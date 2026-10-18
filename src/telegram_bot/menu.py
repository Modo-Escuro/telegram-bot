"""Botões de navegação; rótulos nunca são enviados ao modelo como ações."""

BUTTONS = {
    "Menu": "/menu",
    "Conectar iFood": "/conectar",
    "Entrar no iFood": "/conectar",
    "Sair da conta iFood": "/ifood",
    "Cancelar login": "/ifood",
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
    "Esvaziar carrinho": "Esvaziar carrinho simulado",
    "Esvaziar sacola": "Esvaziar carrinho simulado",
    "Remover pessoa": "/remover",
    "Limpar perfil": "/limpar",
}


def keyboard(*, access=False, cart=False, connection=None):
    rows = [["Menu"]]
    return {
        "keyboard": [[{"text": label} for label in row] for row in rows],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def inline_menu(*, access=False, cart=False):
    rows = (
        [[("Entrar na demo", "enter")]]
        if access
        else [
            [("Conta iFood", "account"), ("Endereços iFood", "addresses")],
            [("Remover pessoa", "remove"), ("Limpar perfil", "clear")],
            *([[("Revisar carrinho", "review")]] if cart else []),
            [("Ajuda", "help"), ("Sair da demo", "exit")],
        ]
    )
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": "nav:" + action} for label, action in row]
            for row in rows
        ]
    }


def navigation(update):
    message = update.get("message")
    if not isinstance(message, dict):
        return update
    text = message.get("text", "")
    command = BUTTONS.get(text) if isinstance(text, str) else None
    return {**update, "message": {**message, "text": command}} if command else update
