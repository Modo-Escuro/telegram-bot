"""Conexão iFood por confirmação humana em botão, sem códigos no chat."""

from dataclasses import dataclass

from .backend import OPAQUE, BackendError

COMMANDS = frozenset({"/conectar", "/confirmar", "/ifood", "/verificar"})
UNCONFIGURED = "A conexão com o iFood ainda não foi configurada nesta demo. Avise o organizador."
NO_PURCHASE = "\nLogin não aprova compras. Sacola e envio ainda indisponíveis neste bot."


@dataclass
class Reply:
    text: str
    markup: dict | None = None


def status_text(status):
    if status.state == "DISCONNECTED":
        text = "Nenhuma conta iFood conectada. Use /conectar."
    elif status.state == "AWAITING_AUTHORIZATION":
        text = "Aguardando login no navegador. Depois envie /confirmar."
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
    if status.state != "AWAITING_CONFIRMATION" or not status.confirmation_id:
        return Reply(text)
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
    return Reply(
        text,
        {
            "inline_keyboard": [
                [
                    {
                        "text": "Confirmar conexão",
                        "callback_data": "ifc:" + status.confirmation_id,
                    }
                ]
            ]
        },
    )


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
    def __init__(self, backend, state):
        self.backend, self.state = backend, state

    def reply(self, command, arguments, update_id):
        if arguments:
            return Reply(f"Use {command} sem argumentos. Não envie códigos ou credenciais no chat.")
        if self.backend is None:
            return Reply(UNCONFIGURED)
        try:
            if command in {"/conectar", "/verificar"} and not self.state.claim_action(update_id):
                return status_reply(self.backend.status())
            if command == "/conectar":
                _, url = self.backend.connect()
                return Reply(
                    "Abra o link e conclua o login no mesmo navegador. "
                    "Se a API estiver em localhost, use o computador em que ela está rodando. "
                    "Depois do login, volte ao Telegram e envie /confirmar para receber "
                    "o botão Confirmar conexão e conferir a conta." + NO_PURCHASE,
                    {"inline_keyboard": [[{"text": "Abrir login do iFood", "url": url}]]},
                )
            if command == "/verificar":
                return status_reply(self.backend.verify())
            return status_reply(self.backend.status())
        except BackendError as error:
            return Reply(error_text(error))

    def confirm_click(self, confirmation_id, update_id):
        if self.backend is None:
            return Reply(UNCONFIGURED)
        if not OPAQUE.fullmatch(confirmation_id):
            return Reply("Confirmação inválida. Envie /confirmar novamente.")
        try:
            if not self.state.claim_action(update_id):
                return status_reply(self.backend.status())
            current = self.backend.status()
            if (
                current.state != "AWAITING_CONFIRMATION"
                or current.confirmation_id != confirmation_id
            ):
                return Reply("Este botão não corresponde à confirmação atual. Envie /confirmar.")
            return status_reply(self.backend.confirm(confirmation_id))
        except BackendError as error:
            if error.kind == "ALREADY_CONFIRMED":
                try:
                    return status_reply(self.backend.status())
                except BackendError as next_error:
                    return Reply(error_text(next_error))
            return Reply(error_text(error))
