"""Botões de navegação; rótulos nunca são enviados ao modelo como ações."""

BUTTONS = {
    "Menu": "/start",
    "Conectar iFood": "/conectar",
    "Minha conexão": "/ifood",
    "Verificar conexão": "/verificar",
    "Acompanhar": "/andamento",
    "Retomar conversa": "/retomar",
    "Interromper": "/interromper",
    "Ajuda": "/ajuda",
    "Endereços iFood": "/enderecos",
    "Revisar carrinho": "/revisarcarrinho",
    "Conferir carrinho": "/conferircarrinho",
    "Sair da demo": "/sair",
}


def keyboard(*, access=False, cart=False):
    rows = (
        [["Entrar na demo"]]
        if access
        else [
            ["Conectar iFood", "Minha conexão"],
            ["Verificar conexão", "Acompanhar"],
            ["Endereços iFood"],
            ["Retomar conversa", "Interromper"],
            *([["Revisar carrinho", "Conferir carrinho"]] if cart else []),
            ["Ajuda", "Sair da demo"],
        ]
    )
    return {
        "keyboard": [[{"text": label} for label in row] for row in rows],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def navigation(update):
    message = update.get("message")
    if not isinstance(message, dict):
        return update
    text = message.get("text", "")
    command = BUTTONS.get(text) if isinstance(text, str) else None
    return {**update, "message": {**message, "text": command}} if command else update
