"""Cliente HTTP v1.0 isolado do polling; RUN-01 ainda precisa oferecer as rotas."""

import math
import re
from dataclasses import dataclass
from functools import wraps
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .backend import MAX_BODY, BackendConfig
from .conversation_contract import (
    Cancellation,
    Document,
    Operation,
    ProtocolError,
    Snapshot,
    check_operation,
    check_snapshot,
    decode,
    encode,
    require,
    utc_now,
    validate,
)
from .telegram import NoRedirect

# Mensagens locais: nunca exibir o texto bruto recebido do servidor/provedor.
ERRORS = {
    "INVALID_REQUEST": (400, "FIX_REQUEST", "Requisição inválida."),
    "UNSUPPORTED_VERSION": (400, "FIX_REQUEST", "Versão do contrato não suportada."),
    "UNAUTHENTICATED": (401, "FIX_REQUEST", "Autenticação necessária."),
    "FORBIDDEN": (403, "NONE", "Acesso não permitido."),
    "NOT_FOUND": (404, "NONE", "Recurso não encontrado."),
    "EVENT_CONFLICT": (409, "FIX_REQUEST", "Evento já recebido com outro conteúdo."),
    "STALE_VERSION": (409, "READ_SNAPSHOT", "A conversa mudou. Consulte a revisão atual."),
    "INVALID_SOURCE": (400, "FIX_REQUEST", "Origem incompatível com a conversa autenticada."),
    "ACTION_UNAVAILABLE": (409, "READ_SNAPSHOT", "Ação indisponível nesta revisão."),
    "REFERENCE_EXPIRED": (410, "READ_SNAPSHOT", "Referência expirada. Consulte a revisão atual."),
    "LINK_CHANGED": (409, "READ_SNAPSHOT", "O vínculo mudou. Uma nova revisão é necessária."),
    "DEADLINE_EXCEEDED": (409, "POLL_OPERATION", "Prazo de processamento excedido."),
    "LIMIT_EXCEEDED": (429, "POLL_OPERATION", "Limite de processamento atingido."),
    "UNAVAILABLE": (503, "POLL_OPERATION", "Serviço temporariamente indisponível."),
    "RESULT_UNKNOWN": (
        409,
        "CONTACT_SUPPORT",
        "Resultado externo desconhecido. Não repita o envio.",
    ),
    "INTERNAL": (500, "POLL_OPERATION", "Não foi possível concluir o processamento."),
    "PROTOCOL": (0, "CONTACT_SUPPORT", "Resposta incompatível com o contrato de conversa."),
}
LEGACY_AUTH = {
    "BOT_API_NOT_CONFIGURED": (503, "UNAVAILABLE"),
    "BOT_AUTH_REQUIRED": (401, "UNAUTHENTICATED"),
    "ORGANIZER_REQUIRED": (400, "INVALID_SOURCE"),
    "ORGANIZER_NOT_ALLOWED": (403, "FORBIDDEN"),
}


class ConversationError(Exception):
    def __init__(self, code: str, *, uncertain: bool = False):
        self.code = code if code in ERRORS else "PROTOCOL"
        self.recovery = ERRORS[self.code][1]
        self.uncertain = uncertain
        super().__init__(ERRORS[self.code][2])


@dataclass(frozen=True)
class PreparedCommand(Document):
    """Corpo exato para a futura outbox. Reenvio explícito conserva chave, versão e origem."""

    schema: str

    def serialize(self) -> bytes:
        return self._raw


def safe_response(*, mutation=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except ProtocolError:
                raise ConversationError("PROTOCOL", uncertain=mutation) from None

        return wrapped

    return decorate


class ConversationClient:
    def __init__(
        self, config: BackendConfig, bot_id: int, *, opener=None, timeout: float = 15, now=utc_now
    ):
        if type(bot_id) is not int or not 0 < bot_id < 10**20 or config.organizer_id >= 10**20:
            raise ValueError("Identidade Telegram inválida.")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("Timeout deve estar entre zero e 60 segundos.")
        self._config = config
        self._bot_id = str(bot_id)
        self._conversation_id = str(config.organizer_id)
        self._opener = opener or build_opener(NoRedirect())
        self._timeout = timeout
        self._now = now

    def _envelope(self, update: dict, expected_version: int, *, callback: bool = False) -> dict:
        # Receber somente updates obtidos pelo transporte Telegram autenticado.
        # O cadastro backend deve vincular bot_id à credencial; não vem do modelo.
        try:
            require(type(update["update_id"]) is int and 0 <= update["update_id"] <= 2**53 - 1)
            query = update["callback_query"] if callback else update["message"]
            message = query["message"] if callback else query
            sender = query["from"]
            require(type(sender["id"]) is int and str(sender["id"]) == self._conversation_id)
            require(sender.get("is_bot") is False and "business_connection_id" not in message)
            require(
                message["chat"]["type"] == "private"
                and type(message["chat"]["id"]) is int
                and str(message["chat"]["id"]) == self._conversation_id
            )
            require(type(message["message_id"]) is int and message["message_id"] > 0)
            source = {
                "channel": "TELEGRAM",
                "botId": self._bot_id,
                "conversationId": self._conversation_id,
                "kind": "CALLBACK" if callback else "MESSAGE",
                "messageId": str(message["message_id"]),
            }
            if callback:
                source["callbackQueryId"] = query["id"]
            return {
                "contractVersion": "1.0",
                "eventId": f"tg-update-{update['update_id']}",
                "conversationId": self._conversation_id,
                "expectedVersion": expected_version,
                "source": source,
            }
        except (KeyError, TypeError, ProtocolError):
            raise ValueError("Update Telegram ou identidade inválidos.") from None

    def prepare_text(self, update: dict, expected_version: int) -> PreparedCommand:
        body = self._envelope(update, expected_version)
        body["input"] = {"kind": "TEXT", "text": update["message"].get("text")}
        return self._prepare("event", body)

    def prepare_action(
        self, update: dict, expected_version: int, *, action: str, action_ref: str
    ) -> PreparedCommand:
        # BOT-03 deve resolver action/action_ref a partir do teclado persistido,
        # sem aceitar referências do texto livre ou do modelo.
        body = self._envelope(update, expected_version, callback=True)
        body["input"] = {"kind": "ACTION", "action": action, "actionRef": action_ref}
        return self._prepare("event", body)

    def prepare_cancel(
        self, update: dict, expected_version: int, operation_id: str
    ) -> PreparedCommand:
        body = self._envelope(update, expected_version, callback="callback_query" in update)
        body["operationId"] = operation_id
        return self._prepare("cancel", body)

    def _scope(self, body: dict) -> None:
        require(body["conversationId"] == self._conversation_id)
        if "source" in body:
            require(
                body["source"]["botId"] == self._bot_id
                and body["source"]["conversationId"] == self._conversation_id
            )

    def _prepare(self, schema: str, body: dict) -> PreparedCommand:
        return self.restore(encode(body), schema)

    def restore(self, raw: bytes, schema: str) -> PreparedCommand:
        """Restaurar bytes de armazenamento confiável sem recriar expectedVersion/eventId."""
        require(schema in {"event", "cancel"} and type(raw) is bytes and len(raw) <= MAX_BODY)
        body = decode(raw)
        validate(schema, body)
        self._scope(body)
        if schema == "cancel":
            require(re.fullmatch(r"[A-Za-z0-9_-]{16,64}", body["operationId"]) is not None)
        if schema == "event":
            require((body["input"]["kind"] == "TEXT") == (body["source"]["kind"] == "MESSAGE"))
        return PreparedCommand(raw, schema)

    @safe_response(mutation=True)
    def send(self, command: PreparedCommand) -> Operation | Cancellation:
        # Também validar comandos restaurados/instanciados pelo chamador.
        command = self.restore(command._raw, command.schema)
        body = command.to_dict()
        if command.schema == "event":
            status, result = self._request("POST", "/events", command._raw)
            operation = self._operation(result)
            require(
                operation.event_id == body["eventId"]
                and operation.base_version == body["expectedVersion"]
            )
            for change in result["changes"]:
                require(change["source"] == body["source"])
            return operation
        target = body["operationId"]
        status, result = self._request("POST", f"/operations/{target}/cancel", command._raw)
        validate("cancelResult", result)
        self._scope(result)
        require(result["eventId"] == body["eventId"] and result["targetOperationId"] == target)
        require((status == 202) == (result["status"] == "REQUESTED"))
        return Cancellation(encode(result), result["status"])

    @safe_response()
    def get_operation(self, operation_id: str, *, event_id: str) -> Operation:
        require(
            isinstance(operation_id, str)
            and re.fullmatch(r"[A-Za-z0-9_-]{16,64}", operation_id) is not None
        )
        _, body = self._request("GET", f"/operations/{operation_id}")
        operation = self._operation(body)
        require(operation.operation_id == operation_id and operation.event_id == event_id)
        return operation

    @safe_response()
    def get_snapshot(self) -> Snapshot:
        _, body = self._request("GET", "")
        validate("snapshot", body)
        self._scope(body)
        check_snapshot(body, self._now())
        return Snapshot(encode(body), body["version"], body["phase"])

    def _operation(self, body: dict) -> Operation:
        validate("operation", body)
        self._scope(body)
        check_operation(body, self._bot_id, self._now())
        return Operation(
            encode(body),
            body["operationId"],
            body["eventId"],
            body["status"],
            body["baseVersion"],
            body["resultVersion"],
            body["pollAfterMs"],
            body["completeness"],
        )

    def _request(self, method: str, suffix: str, raw: bytes | None = None) -> tuple[int, dict]:
        request = Request(
            self._config.base_url.rstrip("/")
            + f"/api/bot/v1/conversations/{self._conversation_id}{suffix}",
            data=raw,
            method=method,
            headers={
                "Authorization": f"Bearer {self._config.token}",
                "X-Telegram-User-Id": self._conversation_id,
                "X-Telegram-Chat-Id": self._conversation_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            try:
                response = self._opener.open(request, timeout=self._timeout)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.status
                content_type = response.headers.get_content_type()
                data = response.read(MAX_BODY + 1)
            require(len(data) <= MAX_BODY and content_type == "application/json")
            body = decode(data)
            if status not in ({200, 202} if method == "POST" else {200}):
                self._raise_error(status, body, method == "POST")
            return status, body
        except ProtocolError:
            raise ConversationError("PROTOCOL", uncertain=method == "POST") from None
        except (OSError, URLError, HTTPException):
            raise ConversationError("UNAVAILABLE", uncertain=method == "POST") from None

    def _raise_error(self, status: int, body: dict, mutation: bool) -> None:
        if set(body) == {"error"} and isinstance(body["error"], dict):
            error = body["error"]
            legacy = (
                LEGACY_AUTH.get(error.get("kind")) if isinstance(error.get("kind"), str) else None
            )
            require(
                set(error) == {"kind", "message"}
                and legacy is not None
                and status == legacy[0]
                and isinstance(error["message"], str)
            )
            raise ConversationError(legacy[1])
        validate("error", body)
        error = body["error"]
        require(
            status == ERRORS[error["code"]][0] and error["recovery"] == ERRORS[error["code"]][1]
        )
        raise ConversationError(
            error["code"],
            uncertain=error["code"] == "RESULT_UNKNOWN" or (mutation and status >= 500),
        )
