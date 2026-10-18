import secrets
import time

from .connections import COMMANDS, Connections
from .telegram import TelegramError

START = (
    "Olá! Sou o bot Compra com Contexto. Esta demo está restrita ao organizador.\n\n"
    "Use /conectar para iniciar o login iFood e /confirmar para conferir a conta. A conversa de compras "
    "ainda está em implementação; nenhum pedido é enviado.\n\n"
    "Use /status para ver o andamento ou /ajuda para os comandos."
)
STATUS = (
    "Telegram: disponível para o organizador autorizado.\n"
    "iFood: use /ifood para consultar a conexão; login não verificado por /status.\n"
    "Sacola e envio de pedidos: indisponíveis."
)
HELP = (
    "/start — iniciar\n/status — estágio da demo\n/ajuda — comandos\n"
    "/conectar — abrir login iFood\n/confirmar — conferir e confirmar por botão\n"
    "/ifood — estado da conexão\n/verificar — verificar sessão no backend"
)


def private_message(update):
    message = update.get("message")
    if not isinstance(message, dict) or message.get("business_connection_id"):
        return None
    sender, chat = message.get("from", {}), message.get("chat", {})
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        return None
    if (
        chat.get("type") != "private"
        or sender.get("is_bot") is not False
        or type(sender.get("id")) is not int
        or sender["id"] <= 0
        or type(chat.get("id")) is not int
        or chat["id"] != sender["id"]
    ):
        return None
    return message


def reply_for(update, allowed_id, username, connections=None):
    message = private_message(update)
    if message is None or message["from"]["id"] != allowed_id:
        return None
    text = message.get("text")
    if not isinstance(text, str):
        return "Nesta etapa, use mensagens de texto: /start, /status ou /ajuda."
    words = text.strip().split()
    command, _, target = (words[0] if words else "").partition("@")
    if target and target.casefold() != username.casefold():
        return None
    if command in COMMANDS:
        return (connections or Connections(None, None)).reply(
            command, words[1:], update["update_id"]
        )
    if command == "/start":
        return START
    if command in {"/ajuda", "/help"}:
        return HELP
    if command == "/status":
        return STATUS
    return "A conversa de compras ainda não está disponível. Use /ajuda para ver os comandos."


def process_batch(api, state, updates, allowed_id, username, connections=None):
    for update in sorted(updates, key=lambda u: u["update_id"]):
        update_id = update["update_id"]
        if type(update_id) is not int:
            raise ValueError("Update Telegram inválido.")
        offset = state.offset()
        if offset is not None and update_id < offset:
            continue
        callback = update.get("callback_query")
        if isinstance(callback, dict):
            process_callback(api, state, callback, update_id, allowed_id, connections)
            state.done(update_id)
            continue
        reply = reply_for(update, allowed_id, username, connections)
        if reply:
            try:
                if isinstance(reply, str):
                    api.send(allowed_id, reply)
                else:
                    api.send(allowed_id, reply.text, reply.markup)
            except TelegramError as exc:
                # Usuário bloqueou o bot; não prender a fila indefinidamente.
                if exc.code != 403:
                    raise
        # Só confirmar depois da resposta ou do descarte deliberado de evento não autorizado.
        state.done(update_id)


def poll(api, state, allowed_id, username, sleep=time.sleep, connections=None):
    delay = 1
    while True:
        try:
            process_batch(
                api, state, api.updates(state.offset()), allowed_id, username, connections
            )
            delay = 1
        except TelegramError as exc:
            if not exc.transient:
                raise
            print("Telegram temporariamente indisponível; aguardando nova tentativa.", flush=True)
            sleep(max(delay, exc.retry_after))
            delay = min(delay * 2, 30)


def identify(api, *, timeout=180, clock=time.monotonic, emit=print):
    """Pareamento local explícito; não grava ID, não autoriza nem envia mensagens."""
    command = "/identificar " + secrets.token_urlsafe(18)
    emit("Envie somente na conversa privada com seu bot, em até 3 minutos:")
    emit(command)
    deadline = clock() + timeout
    offset = None
    while clock() < deadline:
        for update in api.updates(offset):
            offset = update["update_id"] + 1
            message = private_message(update)
            if clock() < deadline and message and message.get("text") == command:
                emit(f"Seu TELEGRAM_ALLOWED_USER_ID é: {message['from']['id']}")
                return message["from"]["id"]
    raise ValueError("Identificação expirou. Execute --identify novamente.")


def process_callback(api, state, callback, update_id, allowed_id, connections):
    sender, message = callback.get("from"), callback.get("message")
    callback_id = callback.get("id")
    if not isinstance(callback_id, str):
        return
    authorized = (
        isinstance(sender, dict)
        and sender.get("is_bot") is False
        and type(sender.get("id")) is int
        and sender["id"] == allowed_id
        and isinstance(message, dict)
        and isinstance(message.get("chat"), dict)
        and message["chat"].get("type") == "private"
        and type(message["chat"].get("id")) is int
        and message["chat"]["id"] == allowed_id
        and type(message.get("message_id")) is int
    )
    try:
        api.call("answerCallbackQuery", {"callback_query_id": callback_id})
    except TelegramError:
        pass  # callback expirado não é autorização; a identidade ainda é verificada acima.
    if not authorized:
        return
    data = callback.get("data")
    if not isinstance(data, str) or not data.startswith("ifc:"):
        return
    reply = (connections or Connections(None, state)).confirm_click(data[4:], update_id)
    api.send(allowed_id, reply.text, reply.markup)
    try:
        api.call(
            "editMessageReplyMarkup",
            {
                "chat_id": allowed_id,
                "message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": []},
            },
        )
    except TelegramError:
        pass  # backend e claim persistente rejeitam repetição mesmo se o teclado permanecer.
