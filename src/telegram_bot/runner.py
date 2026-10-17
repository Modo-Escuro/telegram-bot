import secrets
import time

from .telegram import TelegramError

START = (
    "Olá! Sou o bot Compra com Contexto. Esta demo está restrita ao organizador.\n\n"
    "O canal Telegram está funcionando. A conversa de compras e a conexão ao iFood "
    "ainda estão em implementação; não consulto contas nem envio pedidos.\n\n"
    "Use /status para ver o andamento ou /ajuda para os comandos."
)
STATUS = (
    "Telegram: disponível para o organizador autorizado.\n"
    "iFood: conexão ainda não implementada neste bot; login não verificado.\n"
    "Sacola e envio de pedidos: indisponíveis."
)
HELP = "/start — iniciar\n/status — consultar estágio da demo\n/ajuda — ver comandos"


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


def reply_for(update, allowed_id, username):
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
    if command == "/start":
        return START
    if command in {"/ajuda", "/help"}:
        return HELP
    if command == "/status":
        return STATUS
    return "A conversa de compras ainda não está disponível. Use /ajuda para ver os comandos."


def process_batch(api, state, updates, allowed_id, username):
    for update in sorted(updates, key=lambda u: u["update_id"]):
        update_id = update["update_id"]
        if type(update_id) is not int:
            raise ValueError("Update Telegram inválido.")
        offset = state.offset()
        if offset is not None and update_id < offset:
            continue
        reply = reply_for(update, allowed_id, username)
        if reply:
            try:
                api.send(allowed_id, reply)
            except TelegramError as exc:
                # Usuário bloqueou o bot; não prender a fila indefinidamente.
                if exc.code != 403:
                    raise
        # Só confirmar depois da resposta ou do descarte deliberado de evento não autorizado.
        state.done(update_id)


def poll(api, state, allowed_id, username, sleep=time.sleep):
    delay = 1
    while True:
        try:
            process_batch(api, state, api.updates(state.offset()), allowed_id, username)
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
