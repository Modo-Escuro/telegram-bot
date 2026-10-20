import secrets
import time

from .cart import COMMANDS as CART_COMMANDS
from .connections import COMMANDS, Connections
from .conversation import ConversationError
from .conversation_contract import ProtocolError
from .conversation_runner import (
    CLEAR_MARKUP,
    CLEAR_QUESTION,
    CLEAR_TEXT,
    MODE_TEXTS,
    SELF_MARKUP,
    SELF_QUESTION,
    SELF_TEXT,
    remove_markup,
    remove_text,
)
from .menu import inline_menu, navigation
from .telegram import TelegramError

GET_STARTED = (
    "Me conte o que você tem em mente e a ocasião. Por exemplo: “Quero um bolo para presentear minha namorada”.\n\n"
    "Em Conta iFood, toque em Entrar no iFood para usar sua conta teste."
)
DEMO_NOTICE = (
    "Conectar a conta não autoriza compras. Preparar o carrinho no iFood exige revisão "
    "e confirmação específicas. Nenhum pedido é enviado."
)
START = "Olá! Eu sou o Ailo, seu assistente de compras.\n\n" + GET_STARTED + "\n\n" + DEMO_NOTICE
STATUS = "Estou por aqui! O login não é verificado nesta tela. Use /ifood para consultar sua conta."
HELP = (
    "• Conta iFood: entre, acompanhe o login ou saia da conta teste.\n"
    "• Endereços iFood: escolha onde receber.\n"
    "• Esvaziar carrinho: limpe a composição da demo.\n"
    "• Remover pessoa / Limpar tudo / Meus dados: apague uma pessoa, todo o pedido ou só o seu perfil.\n"
    "• Sair da demo: encerre seu acesso.\n\n"
    "Faltou uma resposta? Use /retomar. Você pode escrever ou usar os botões das mensagens."
)


PROFILE_COMMANDS = frozenset({"/limpar", "/limpadados", "/remover"})
NO_PEOPLE = "Não há pessoas salvas neste pedido."


def profile_command(api, state, allowed_id, action, conversations):
    """Abre a confirmação por botão; nada é apagado sem o clique."""
    if conversations is None:
        api.send(allowed_id, "A conversa de compras não está disponível nesta configuração.")
        return
    try:
        context, names = conversations.profile_context()
    except (ConversationError, ValueError, ProtocolError, OSError):
        api.send(allowed_id, "Não consegui consultar o pedido agora. Tente de novo em instantes.")
        return
    if action == "/limpar":
        sent = api.send(allowed_id, CLEAR_QUESTION, CLEAR_MARKUP)
        kind, names = "clear", []
    elif action == "/limpadados":
        sent = api.send(allowed_id, SELF_QUESTION, SELF_MARKUP)
        kind = "self"
    else:
        if not names:
            api.send(allowed_id, NO_PEOPLE)
            return
        sent = api.send(allowed_id, "Quem você quer remover do pedido?", remove_markup(names))
        kind = "remove"
    if isinstance(sent, dict) and type(sent.get("message_id")) is int:
        state.confirm_prompt(sent["message_id"], kind, names)
        state.bind_prompt(sent["message_id"], context)


def profile_click(api, state, allowed_id, callback, update_id, data, conversations):
    """Clique já autorizado (remetente/chat privado). Uso único por teclado; depois remove o teclado."""
    message = callback["message"]
    kind = "clear" if data.startswith("clr:") else "self" if data.startswith("se:") else "remove"
    choice = data.split(":", 1)[1]
    names = state.claim_confirm(message["message_id"], kind)
    text = None
    if names is not None and choice != "no":
        if kind == "clear" and choice == "yes":
            text, reply = CLEAR_TEXT, "Certo: vou apagar os dados deste pedido."
        elif kind == "self" and choice == "yes":
            text, reply = SELF_TEXT, "Certo: vou apagar seus dados desta memória."
        elif kind == "remove" and choice.isdigit() and int(choice) < len(names):
            name = names[int(choice)]
            text, reply = remove_text(name), f"Certo: vou remover {name} do pedido."
    if names is None:
        reply = "Esta confirmação expirou ou já foi usada. Nada foi apagado."
    elif text is None:
        reply = "Cancelado. Nada foi apagado."
    elif conversations is not None:
        try:
            context = state.prompt_context(message["message_id"])
            if context is None:
                raise ValueError("Confirmação expirada")
            conversations.text_click(callback, update_id, text, "tg-" + kind + "-", context)
        except (ConversationError, ValueError, ProtocolError):
            reply = "Não consegui enviar a confirmação. Nada foi apagado; tente de novo."
    api.send(allowed_id, reply)
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
        pass


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
    update = navigation(update)
    message = private_message(update)
    if message is None or message["from"]["id"] != allowed_id:
        return None
    text = message.get("text")
    if not isinstance(text, str):
        return "Por enquanto, escreva uma mensagem ou toque em Ajuda."
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
    if command == "/menu":
        return "O que você quer fazer?"
    if command in {"/ajuda", "/help"}:
        return HELP
    if command == "/status":
        return STATUS
    return "A conversa de compras não está disponível nesta configuração. Toque em Ajuda."


def process_batch(
    api, state, updates, allowed_id, username, connections=None, conversations=None, carts=None
):
    for update in sorted(updates, key=lambda u: u["update_id"]):
        update = navigation(update)
        update_id = update["update_id"]
        if type(update_id) is not int:
            raise ValueError("Update Telegram inválido.")
        offset = state.offset()
        if offset is not None and update_id < offset:
            continue
        callback = update.get("callback_query")
        if isinstance(callback, dict):
            process_callback(
                api,
                state,
                callback,
                update_id,
                allowed_id,
                connections,
                conversations=conversations,
                carts=carts,
            )
            state.done(update_id)
            continue
        message = private_message(update)
        if message and message["from"]["id"] == allowed_id:
            raw = message.get("text", "")
            word = raw.strip().split(maxsplit=1)[0] if isinstance(raw, str) and raw.strip() else ""
            action, _, target = word.partition("@")
            if action in CART_COMMANDS and (not target or target.casefold() == username.casefold()):
                text = (
                    carts.receive(action)
                    if carts
                    else "Preparação de carrinho indisponível nesta configuração."
                )
                api.send(allowed_id, text)
                state.done(update_id)
                continue
            if carts:
                carts.invalidate()
            if action in PROFILE_COMMANDS and (
                not target or target.casefold() == username.casefold()
            ):
                profile_command(api, state, allowed_id, action, conversations)
                state.done(update_id)
                continue
        if conversations is not None and message and message["from"]["id"] == allowed_id:
            text = message.get("text")
            first = (
                text.strip().split(maxsplit=1)[0] if isinstance(text, str) and text.strip() else ""
            )
            command, _, target = first.partition("@")
            if not first.startswith("/"):
                command, target = first, ""
            if (not target or target.casefold() == username.casefold()) and (
                command in conversations.COMMANDS
                or (first and not first.startswith("/"))
                or "voice" in message
            ):
                try:
                    reply = conversations.receive(
                        update, command if command.startswith("/") else None
                    )
                except (ValueError, ProtocolError):
                    reply = "Mensagem não aceita: confira o tamanho e o formato. Nenhuma alteração foi enviada."
                if reply:
                    try:
                        api.send(allowed_id, reply)
                    except TelegramError as exc:
                        if exc.code != 403:
                            raise
                    state.done(update_id)
                # A outbox já gravou o cursor atomicamente, ou a recusa foi respondida acima.
                continue
        reply = reply_for(update, allowed_id, username, connections)
        if conversations is not None and reply == START and conversations.voice_enabled:
            reply += "\n\nPode enviar áudios de até um minuto. Uso a Groq para transcrever e mostro o texto para você conferir."
        if reply:
            try:
                if isinstance(reply, str):
                    api.send(
                        allowed_id,
                        reply,
                        inline_menu(cart=carts is not None)
                        if reply.startswith(START) or reply in {HELP, "O que você quer fazer?"}
                        else None,
                    )
                else:
                    if reply.connection_state and hasattr(api, "set_connection_state"):
                        api.set_connection_state(allowed_id, reply.connection_state)
                    result = api.send(allowed_id, reply.text, reply.markup)
                    if connections is not None:
                        connections.delivered(reply, result)
            except TelegramError as exc:
                # Usuário bloqueou o bot; não prender a fila indefinidamente.
                if exc.code != 403:
                    raise
        # Só confirmar depois da resposta ou do descarte deliberado de evento não autorizado.
        state.done(update_id)


def poll(
    api,
    state,
    allowed_id,
    username,
    sleep=time.sleep,
    connections=None,
    conversations=None,
    service=None,
    carts=None,
):
    delay = 1
    while True:
        try:
            if service is not None and service.failed.is_set():
                raise ValueError(
                    "Worker de conversa indisponível; reinicie após verificar armazenamento/configuração."
                )
            updates = (
                api.updates(state.offset(), timeout=3)
                if conversations is not None or (connections is not None and connections.watching)
                else api.updates(state.offset())
            )
            process_batch(
                api, state, updates, allowed_id, username, connections, conversations, carts
            )
            if carts is not None:
                carts.tick(api)
            if connections is not None:
                connections.tick(api, allowed_id)
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


def process_callback(
    api, state, callback, update_id, allowed_id, connections, conversations=None, carts=None
):
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
    if isinstance(data, str) and data.startswith("nav:"):
        if (
            message.get("forward_origin")
            or not isinstance(message.get("from"), dict)
            or message["from"].get("is_bot") is not True
        ):
            return
        action = data[4:]
        if action in {"remove", "clear", "self"}:
            profile_command(
                api,
                state,
                allowed_id,
                {"remove": "/remover", "clear": "/limpar", "self": "/limpadados"}[action],
                conversations,
            )
        elif action in {"account", "connect"}:
            handler = connections or Connections(None, state)
            reply = handler.reply("/conectar" if action == "connect" else "/ifood", [], update_id)
            result = api.send(allowed_id, reply.text, reply.markup)
            handler.delivered(reply, result)
        elif action == "addresses" and conversations:
            queued = conversations.box.enqueue_addresses("menu-" + str(update_id))
            api.send(
                allowed_id,
                "Vou conferir seus endereços."
                if queued
                else "Aguarde a resposta anterior e tente novamente.",
            )
        elif action == "review" and carts:
            api.send(allowed_id, carts.receive("/revisarcarrinho"))
        elif action in {"help", "menu"}:
            api.send(
                allowed_id,
                HELP if action == "help" else "O que você quer fazer?",
                inline_menu(cart=carts is not None),
            )
        elif action == "exit":
            api.send(
                allowed_id,
                "Sair da demo está disponível no acesso por senha. Para sair do iFood, abra Conta iFood.",
                inline_menu(),
            )
        return
    if isinstance(data, str) and data.startswith("cv:"):
        reply = (
            conversations.flow_click(callback, update_id, carts)
            if conversations
            else "Conversa indisponível nesta configuração."
        )
        if reply:
            api.send(allowed_id, reply)
        return
    if isinstance(data, str) and data.startswith("ifa:"):
        queued = conversations and conversations.address_click(callback, update_id)
        api.send(
            allowed_id,
            "Vou validar o endereço escolhido na conta conectada."
            if queued
            else "Esta escolha expirou ou não corresponde à mensagem original. Toque em Endereços iFood.",
        )
        return
    if isinstance(data, str) and data.startswith(("clr:", "rm:", "se:")):
        profile_click(api, state, allowed_id, callback, update_id, data, conversations)
        return
    if isinstance(data, str) and data.startswith("mode:"):
        choice = data.removeprefix("mode:")
        ok = (
            conversations is not None
            and choice in MODE_TEXTS
            and state.claim_mode(message["message_id"])
        )
        if ok:
            try:
                conversations.mode_click(
                    callback, update_id, choice, state.prompt_context(message["message_id"])
                )
            except (ConversationError, ValueError, ProtocolError):
                ok = False
        api.send(
            allowed_id,
            ("Certo: pedido só para você." if choice == "individual" else "Certo: pedido em grupo.")
            if ok
            else "Esta escolha expirou ou já foi usada. Pode escrever direto para quem é o pedido.",
        )
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
            pass
        return
    if isinstance(data, str) and data.startswith("cart:"):
        text = (
            carts.click(callback)
            if carts
            else "Preparação de carrinho indisponível nesta configuração."
        )
        api.send(allowed_id, text)
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
            pass
        return
    if not isinstance(data, str) or not data.startswith(("ifc:", "ifx:", "ifd:")):
        return
    handler = connections or Connections(None, state)
    reply = handler.action_click(data, update_id)
    if reply.connection_state and hasattr(api, "set_connection_state"):
        api.set_connection_state(allowed_id, reply.connection_state)
    result = api.send(allowed_id, reply.text, reply.markup)
    handler.delivered(reply, result)
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
