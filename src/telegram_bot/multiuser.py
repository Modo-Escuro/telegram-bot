"""Um polling Telegram, sessões isoladas por usuário admitido com a senha da demo."""

import hashlib
import time
from dataclasses import replace

from .access import AccessStore
from .backend import Backend, BackendConfig
from .connections import Connections
from .conversation import ConversationClient
from .conversation_runner import Conversations, ConversationService, scope_for
from .outbox import Outbox
from .runner import private_message, process_batch
from .state import State
from .telegram import Telegram, TelegramError

PROMPT = "Bem-vindo! Para liberar a demo, envie /entrar seguido da senha compartilhada pela equipe. Use somente esta conversa privada."


def private_owner(update):
    message = private_message(update)
    if message:
        return message["from"]["id"]
    callback = update.get("callback_query")
    if not isinstance(callback, dict):
        return None
    sender, message = callback.get("from"), callback.get("message")
    if not isinstance(sender, dict) or not isinstance(message, dict):
        return None
    # Reutiliza a mesma validação de origem da mensagem; callback não vira autorização.
    candidate = {"message": {**message, "from": sender}}
    message = private_message(candidate)
    return message["from"]["id"] if message else None


class UserSession:
    def __init__(self, config, bot_id, owner, access_check):
        self.owner, self.box, self.service = owner, None, None
        # A cópia original conserva cursor, fila e acompanhamento do organizador anterior.
        legacy = config.state_dir / f"bot-{bot_id}.sqlite3"
        if owner == config.allowed_user_id:
            path = legacy
        else:
            key = hashlib.sha256(f"{bot_id}|{owner}".encode()).hexdigest()
            folder = config.state_dir / "users" / key
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = folder / "bot.sqlite3"
        self.state = State(path)
        try:
            backend_cfg = BackendConfig.from_env(owner)
            backend_cfg = replace(backend_cfg, password_access=True) if backend_cfg else None
            conversations = None
            if config.conversation_enabled:
                if backend_cfg is None:
                    raise ValueError("Conversa requer configuração do backend.")
                scope = scope_for(backend_cfg, bot_id)
                client_factory = lambda: ConversationClient(backend_cfg, bot_id, timeout=5)
                self.box = Outbox(path, scope)
                conversations = Conversations(self.box, client_factory())
                self.service = ConversationService(
                    path,
                    scope,
                    client_factory,
                    lambda: Telegram(config.token, timeout=5),
                    owner,
                    link_status_factory=lambda: lambda: Backend(backend_cfg).status(timeout=5),
                    access_allowed_factory=lambda: access_check,
                )
                self.service.start()
            self.connections = Connections(
                Backend(backend_cfg) if backend_cfg else None,
                self.state,
                owner,
                conversations=conversations,
            )
            self.conversations = conversations
        except BaseException:
            self.close()
            raise

    def receive(self, api, update, username):
        process_batch(
            api, self.state, [update], self.owner, username, self.connections, self.conversations
        )

    def tick(self, api):
        if self.service and self.service.failed.is_set():
            raise ValueError("Worker de conversa indisponível; conferir armazenamento.")
        self.connections.tick(api, self.owner)

    def close(self):
        try:
            if self.service:
                self.service.stop()
        finally:
            if self.box:
                self.box.close()
            self.state.close()


class PasswordRouter:
    def __init__(self, config, bot_id, state, *, session_factory=UserSession):
        self.config, self.bot_id, self.state = config, bot_id, state
        self.access = AccessStore(
            config.state_dir / f"bot-{bot_id}-access.sqlite3",
            config.access_password,
            config.token,
            capacity=config.access_max_users,
        )
        self.sessions, self.factory, self.position = {}, session_factory, 0

    def session(self, owner):
        if owner not in self.sessions:
            self.sessions[owner] = self.factory(
                self.config, self.bot_id, owner, self.access.checker(owner)
            )
        return self.sessions[owner]

    def receive(self, api, updates, username):
        for update in sorted(updates, key=lambda u: u["update_id"]):
            number = update["update_id"]
            if type(number) is not int:
                raise ValueError("Update Telegram inválido.")
            offset = self.state.offset()
            if offset is not None and number < offset:
                continue
            owner = private_owner(update)
            if owner is None:
                self.state.done(number)
                continue
            message = private_message(update)
            text = message.get("text", "") if message else ""
            words = text.strip().split(maxsplit=1) if isinstance(text, str) else []
            command, _, target = (words[0] if words else "").partition("@")
            if target and target.casefold() != username.casefold():
                self.state.done(number)
                continue
            if command == "/entrar":
                # A senha nunca entra na outbox, no modelo nem no banco. Apagar a mensagem é best effort.
                if type(message.get("message_id")) is int:
                    try:
                        api.call(
                            "deleteMessage", {"chat_id": owner, "message_id": message["message_id"]}
                        )
                    except TelegramError:
                        pass
                result = self.access.enter(owner, words[1] if len(words) > 1 else "")
                reply = {
                    "OK": "Acesso à demo liberado por 24 horas! Para consultar o iFood, use /conectar e autorize uma conta de teste do evento no navegador, depois confirme no botão humano. A senha da demo não substitui esse login. Use /ajuda para comandos e /sair para encerrar o acesso. Login não aprova compras.",
                    "DENIED": "Senha incorreta. Confira com a equipe e tente novamente.",
                    "LIMIT": "Limite de tentativas atingido. Aguarde 15 minutos antes de tentar novamente.",
                    "FULL": "A demo atingiu o limite de sessões simultâneas. Tente novamente mais tarde.",
                }[result]
                if result == "OK":
                    self.session(owner)
                # A tentativa já está gravada: falha Telegram pode repetir orientação, nunca enviar a senha.
                self.send(api, owner, reply)
            elif command == "/sair":
                self.access.revoke(owner)
                if owner in self.sessions:
                    self.sessions.pop(owner).close()
                self.send(
                    api,
                    owner,
                    "Acesso à demo encerrado. Seu vínculo iFood não foi desconectado. Para remover o vínculo, entre novamente e use /desconectar.",
                )
            elif self.access.allowed(owner):
                self.session(owner).receive(api, update, username)
            elif self.access.notice(owner):
                self.send(api, owner, PROMPT)
            self.state.done(number)

    @staticmethod
    def send(api, owner, text):
        try:
            api.send(owner, text)
        except TelegramError as exc:
            if exc.code != 403:
                raise

    def tick(self, api):
        owners = self.access.owners()
        for owner in list(self.sessions):
            if owner not in owners:
                self.sessions.pop(owner).close()
        # Reconstrução após reinício: a fila/login de cada usuário continua no mesmo arquivo.
        for owner in owners:
            self.session(owner)
        if owners:
            self.position = (self.position + 1) % len(owners)
            self.sessions[owners[self.position]].tick(api)

    def close(self):
        try:
            for session in self.sessions.values():
                session.close()
        finally:
            self.access.close()


def poll_password(api, state, config, bot_id, username, *, sleep=time.sleep):
    router = PasswordRouter(config, bot_id, state)
    delay = 1
    try:
        while True:
            try:
                router.tick(api)
                updates = api.updates(state.offset(), timeout=3)
                router.receive(api, updates, username)
                delay = 1
            except TelegramError as exc:
                if not exc.transient:
                    raise
                sleep(max(delay, exc.retry_after))
                delay = min(delay * 2, 30)
    finally:
        router.close()
