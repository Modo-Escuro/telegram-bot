"""Conexão iFood por confirmação humana em botão, sem códigos no chat."""

from dataclasses import dataclass, field

from .backend import OPAQUE, BackendError

COMMANDS = frozenset(
    {"/conectar", "/confirmar", "/ifood", "/verificar", "/cancelar", "/desconectar"}
)
UNCONFIGURED = "A conexão com o iFood ainda não foi configurada nesta demo. Avise o organizador."
NO_PURCHASE = "\nLogin não aprova compras. Sacola e envio ainda indisponíveis neste bot."


@dataclass
class Reply:
    text: str
    markup: dict | None = None
    watch_attempt: str | None = field(default=None, repr=False)
    watch_phase: str = field(default="", repr=False)


def status_text(status):
    if status.state == "DISCONNECTED":
        text = "Nenhuma conta iFood conectada. Use /conectar."
    elif status.state == "AWAITING_AUTHORIZATION":
        text = (
            "Aguardando login no navegador. O botão será atualizado aqui; /confirmar é alternativa."
        )
    elif status.state == "AWAITING_CONFIRMATION":
        text = "Autorização recebida. Confira a conta e toque em Confirmar conexão."
    elif status.state == "RECONNECT_REQUIRED":
        text = "A sessão precisa de novo login. Use /conectar."
    elif status.state == "UNAVAILABLE":
        text = "iFood indisponível no momento; isso não significa logout. Tente /verificar depois."
    elif status.operational and status.allowed_operations:
        text = "Conta iFood vinculada e sessão verificada pelo backend."
    else:
        text = "Conta vinculada, mas acesso ainda não liberado. Use /verificar; podem faltar permissões."
    return text + NO_PURCHASE


def status_reply(status):
    text = status_text(status)
    buttons = []
    if status.state == "AWAITING_CONFIRMATION" and status.confirmation_id:
        identity = status.identity or {}
        if identity.get("status") == "VERIFIED":
            fields = [identity.get("displayName"), identity.get("emailMasked")]
            labels = [s for s in fields if isinstance(s, str) and 0 < len(s) <= 150]
            text += "\nConta informada pelo backend: " + (
                " · ".join(labels) or "identidade indisponível"
            )
        else:
            text += "\nNão foi possível verificar a identidade da conta."
        text += "\nConfirme somente se reconhece a conta que acabou de autorizar."
        buttons.append(
            [{"text": "Confirmar conexão", "callback_data": "ifc:" + status.confirmation_id}]
        )
    if status.attempt_id and len(status.attempt_id) <= 60:
        buttons.append(
            [{"text": "Cancelar tentativa", "callback_data": "ifx:" + status.attempt_id}]
        )
    if status.link_id and len(status.link_id) <= 60:
        buttons.append([{"text": "Desconectar vínculo", "callback_data": "ifd:" + status.link_id}])
    return Reply(text, {"inline_keyboard": buttons} if buttons else None)


def error_text(error):
    if error.uncertain:
        return (
            "Não foi possível confirmar o resultado da solicitação. "
            "Não a repetirei automaticamente. Consulte /ifood antes de enviar outro comando."
        )
    messages = {
        "BOT_API_NOT_CONFIGURED": "A integração do bot não está configurada na API.",
        "BOT_AUTH_REQUIRED": "A API recusou a credencial do bot. Avise o organizador.",
        "ORGANIZER_REQUIRED": "A API não reconheceu a identidade do organizador.",
        "ORGANIZER_NOT_ALLOWED": "Este organizador não está autorizado na API.",
        "IFOOD_CLIENT_NOT_CONFIGURED": "O login iFood ainda não foi configurado no backend.",
        "AUTHORIZATION_PENDING": "Conclua o login no navegador antes de confirmar.",
        "ATTEMPT_EXPIRED": "A tentativa expirou. Use /conectar para gerar outra.",
        "ATTEMPT_USED": "A tentativa já foi usada ou substituída. Consulte /ifood.",
        "ATTEMPT_NOT_FOUND": "Tentativa não encontrada. Use /conectar.",
        "CONFIRMATION_NOT_FOUND": "Confirmação não encontrada. Consulte /ifood.",
        "CONFIRMATION_EXPIRED": "Confirmação expirada. Use /conectar.",
        "CONFIRMATION_INVALID": "Confirmação cancelada ou substituída. Consulte /ifood.",
        "ALREADY_CONFIRMED": "Conexão já confirmada. Consulte /ifood.",
        "IFOOD_LINK_REQUIRED": "Conecte sua conta primeiro com /conectar.",
        "IFOOD_RECONNECT_REQUIRED": "É necessário refazer o login com /conectar.",
        "IFOOD_SCOPE_MISSING": "A sessão não tem as permissões necessárias.",
        "IFOOD_UNAVAILABLE": "iFood indisponível. Tente /verificar mais tarde.",
        "PROTOCOL": "A API retornou uma resposta incompatível. Avise o organizador.",
    }
    return messages.get(error.kind, "Não consegui consultar a API. Confira se ela está disponível.")


class Connections:
    def __init__(self, backend, state, organizer_id=None):
        self.backend, self.state = backend, state
        self.organizer_id = organizer_id

    def _present(self, status):
        reply = status_reply(status)
        if self.organizer_id is None:
            return reply
        if status.attempt_id:
            self.state.watch_login(
                self.organizer_id,
                status.attempt_id,
                status.attempt_expires_at
                if status.attempt_expires_at is not None
                else self.state.clock() + 600,
            )
            reply.watch_attempt, reply.watch_phase = status.attempt_id, status.state
        else:
            self.state.stop_login_watch()
        return reply

    def delivered(self, reply, result):
        if (
            reply.watch_attempt
            and isinstance(result, dict)
            and type(result.get("message_id")) is int
            and result["message_id"] > 0
        ):
            self.state.login_message(reply.watch_attempt, result["message_id"], reply.watch_phase)

    @property
    def watching(self):
        return (
            self.backend is not None
            and self.organizer_id is not None
            and self.state.login_watch() is not None
        )

    def reply(self, command, arguments, update_id):
        if arguments:
            return Reply(f"Use {command} sem argumentos. Não envie códigos ou credenciais no chat.")
        if self.backend is None:
            return Reply(UNCONFIGURED)
        try:
            if command in {
                "/conectar",
                "/verificar",
                "/cancelar",
                "/desconectar",
            } and not self.state.claim_action(update_id):
                return self._present(self.backend.status())
            if command == "/conectar":
                status, url = self.backend.connect()
                reply = self._present(status)
                reply.text = (
                    "Abra o link e conclua o login no mesmo navegador. "
                    "Se a API estiver em localhost, use o computador em que ela está rodando. "
                    "Depois volte a esta mensagem: o botão Confirmar conexão aparecerá aqui. "
                    "Se não aparecer, envie /confirmar para conferir a conta." + NO_PURCHASE
                )
                rows = (reply.markup or {}).get("inline_keyboard", [])
                reply.markup = {
                    "inline_keyboard": [[{"text": "Abrir login do iFood", "url": url}], *rows]
                }
                return reply
            if command == "/verificar":
                return self._present(self.backend.verify())
            if command == "/cancelar":
                return self._cancel()
            if command == "/desconectar":
                return self._disconnect()
            return self._present(self.backend.status())
        except BackendError as error:
            return Reply(error_text(error))

    def confirm_click(self, confirmation_id, update_id):
        if self.backend is None:
            return Reply(UNCONFIGURED)
        if not OPAQUE.fullmatch(confirmation_id):
            return Reply("Confirmação inválida. Envie /confirmar novamente.")
        try:
            if not self.state.claim_action(update_id):
                return self._present(self.backend.status())
            current = self.backend.status()
            if (
                current.state != "AWAITING_CONFIRMATION"
                or current.confirmation_id != confirmation_id
            ):
                return Reply("Este botão não corresponde à confirmação atual. Envie /confirmar.")
            return self._present(self.backend.confirm(confirmation_id))
        except BackendError as error:
            if error.kind == "ALREADY_CONFIRMED":
                try:
                    return self._present(self.backend.status())
                except BackendError as next_error:
                    return Reply(error_text(next_error))
            return Reply(error_text(error))

    def _cancel(self):
        status, cancelled = self.backend.cancel()
        reply = self._present(status)
        reply.text = ("Tentativa cancelada." if cancelled else "Não havia tentativa pendente.") + (
            " O cancelamento preserva um vínculo já confirmado.\n" + reply.text
        )
        return reply

    def _disconnect(self):
        status, removed = self.backend.disconnect()
        reply = self._present(status)
        reply.text = ("Vínculo local removido." if removed else "Não havia vínculo local.") + (
            " Não foi solicitada revogação no provedor. "
            "Uma tentativa de login pendente continua; use /cancelar para encerrá-la.\n"
            + reply.text
        )
        return reply

    def action_click(self, data, update_id):
        if data.startswith("ifc:"):
            return self.confirm_click(data[4:], update_id)
        if self.backend is None:
            return Reply(UNCONFIGURED)
        prefix, _, reference = data.partition(":")
        if prefix not in {"ifx", "ifd"} or not OPAQUE.fullmatch(reference):
            return Reply("Ação inválida. Consulte /ifood.")
        try:
            if not self.state.claim_action(update_id):
                return self._present(self.backend.status())
            status = self.backend.status()
            current = status.attempt_id if prefix == "ifx" else status.link_id
            if current != reference:
                return Reply(
                    "Este botão não corresponde à tentativa ou ao vínculo atual. Consulte /ifood."
                )
            return self._cancel() if prefix == "ifx" else self._disconnect()
        except BackendError as error:
            return Reply(error_text(error))

    def tick(self, api, allowed_id):
        """Somente GET; edita uma mensagem conhecida, sem repetir notificações por envio."""
        if not self.watching:
            return
        watch = self.state.login_watch()
        now = self.state.clock()
        if watch["owner"] != allowed_id or self.organizer_id != allowed_id:
            self.state.stop_login_watch()
            return
        if now < watch["next_check"]:
            return
        self.state.login_next_check(now + 5)
        if now >= watch["started"] + 1200:
            self._finish_watch(
                api, allowed_id, watch, "Acompanhamento encerrado. Consulte /ifood ou /confirmar."
            )
            return
        try:
            status = self.backend.status(timeout=5)
        except BackendError:
            if now >= watch["expires"]:
                self._finish_watch(
                    api,
                    allowed_id,
                    watch,
                    "Não consegui acompanhar o login. Consulte /ifood ou /confirmar.",
                )
            return
        if status.attempt_id != watch["attempt_id"]:
            text = (
                status_text(status)
                if not status.attempt_id
                else ("Esta tentativa foi substituída. Consulte /ifood para acompanhar a atual.")
            )
            self._finish_watch(api, allowed_id, watch, text)
            return
        expires = min(
            status.attempt_expires_at
            if status.attempt_expires_at is not None
            else watch["expires"],
            watch["started"] + 1200,
        )
        if now >= expires:
            self._finish_watch(
                api,
                allowed_id,
                watch,
                "A tentativa expirou. Consulte /ifood e use /conectar se necessário.",
            )
            return
        if watch["phase"] != status.state and watch["message_id"]:
            reply = status_reply(status)
            if not self._edit(api, allowed_id, watch, reply):
                return
            self.state.login_phase(status.state, expires)
        else:
            self.state.login_phase(watch["phase"], expires)

    def _edit(self, api, allowed_id, watch, reply):
        from .telegram import TelegramError

        try:
            api.call(
                "editMessageText",
                {
                    "chat_id": allowed_id,
                    "message_id": watch["message_id"],
                    "text": reply.text,
                    "reply_markup": reply.markup or {"inline_keyboard": []},
                },
            )
            return True
        except TelegramError as error:
            if error.transient:
                self.state.login_next_check(self.state.clock() + max(5, error.retry_after))
            else:
                self.state.stop_login_watch()
            return False

    def _finish_watch(self, api, allowed_id, watch, text):
        if watch["message_id"]:
            self._edit(api, allowed_id, watch, Reply(text))
        self.state.stop_login_watch()
