"""Cliente do contrato CART-01. Não executa OAuth, pagamento ou envio de pedido."""

import re
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .conversation_contract import ProtocolError, decode, encode, require
from .telegram import NoRedirect

OPAQUE = re.compile(r"[A-Za-z0-9_-]{32}")
UUID = re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}")
STATES = {"PENDING", "SUCCEEDED", "FAILED", "RESULT_UNKNOWN"}
TOOLS = {"createCart", "addItemToCart", "updateCartItem", "removeItemFromCart"}


class CartError(Exception):
    def __init__(self, code="UNAVAILABLE", *, uncertain=False):
        self.code = code
        self.uncertain = uncertain
        super().__init__("Não foi possível concluir a operação de carrinho com segurança.")


class CartClient:
    def __init__(self, config, *, opener=None, timeout=5):
        self.config = config
        self.opener = opener or build_opener(NoRedirect())
        self.timeout = timeout

    def _request(self, method, suffix, body=None):
        request = Request(
            self.config.base_url.rstrip("/")
            + f"/api/bot/v1/conversations/{self.config.organizer_id}/cart-writes/{suffix}",
            data=encode(body) if body is not None else None,
            method=method,
            headers={
                "Authorization": "Bearer " + self.config.token,
                "X-Telegram-User-Id": str(self.config.organizer_id),
                "X-Telegram-Chat-Id": str(self.config.organizer_id),
                **({"X-Telegram-Access": "PASSWORD"} if self.config.password_access else {}),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read(65_537)
                status = response.status
                require(len(raw) <= 65_536)
                require(response.headers.get_content_type() == "application/json")
            value = decode(raw)
            if status != 200:
                kind = value.get("error", {}).get("kind")
                # Mensagem remota nunca é exibida. Só códigos fixos controlam recuperação.
                known = {
                    "CART_INTENT_NOT_FOUND",
                    "CART_FEATURE_DISABLED",
                    "CART_CONTRACT_UNVERIFIED",
                    "CART_ALREADY_MATCHES",
                    "CART_GROUP_BLOCKED",
                    "CART_ITEM_BLOCKED",
                    "CART_REVIEW_CHANGED",
                    "CART_LINK_CHANGED",
                    "CART_CONFIRMATION_EXPIRED",
                    "RESULT_UNKNOWN",
                    "INVALID_SOURCE",
                }
                raise CartError(
                    kind if kind in known else "UNAVAILABLE",
                    uncertain=method == "POST" and suffix == "confirm" and status >= 500,
                )
            return value
        except CartError:
            raise
        except (ProtocolError, ValueError, TypeError, AttributeError):
            raise CartError(
                "PROTOCOL", uncertain=method == "POST" and suffix == "confirm"
            ) from None
        except (OSError, URLError, HTTPException):
            raise CartError(uncertain=method == "POST" and suffix == "confirm") from None

    def review(self):
        value = self._request("POST", "reviews", {})
        try:
            require(value.get("purpose") == "PREPARE_CART")
            require(
                value.get("purchaseAuthorized") is False and value.get("checkoutEnabled") is False
            )
            require(
                isinstance(value.get("confirmationRef"), str)
                and OPAQUE.fullmatch(value["confirmationRef"])
            )
            require(type(value.get("version")) is int and value["version"] >= 0)
            require(
                isinstance(value.get("fingerprint"), str)
                and re.fullmatch(r"[a-f0-9]{64}", value["fingerprint"])
            )
            require(value.get("totalCents") is None and value.get("unknownCosts") is True)
            require(
                type(value.get("observedSubtotalCents")) is int
                and 0 <= value["observedSubtotalCents"] <= 2**53 - 1
            )
            require(isinstance(value.get("lines"), list) and 0 < len(value["lines"]) <= 100)
            require(isinstance(value.get("changes"), list) and 0 < len(value["changes"]) <= 40)
            require(
                all(
                    isinstance(step, dict) and step.get("tool") in TOOLS
                    for step in value["changes"]
                )
            )
            return value
        except ProtocolError:
            raise CartError("PROTOCOL") from None

    @staticmethod
    def operation(value):
        try:
            require(value.get("purpose") == "PREPARE_CART" and value.get("state") in STATES)
            require(
                value.get("purchaseAuthorized") is False and value.get("checkoutEnabled") is False
            )
            require(value.get("paymentEnabled") is False)
            require(
                isinstance(value.get("operationId"), str) and OPAQUE.fullmatch(value["operationId"])
            )
            require(
                type(value.get("completedOperations")) is int
                and 0 <= value["completedOperations"] <= 40
            )
            # A projeção descarta carrinho bruto e dados que não serão apresentados pelo bot.
            return {key: value[key] for key in ("operationId", "state", "completedOperations")}
        except (ProtocolError, TypeError):
            raise CartError("PROTOCOL", uncertain=True) from None

    def confirm(self, reference, request_id, callback_id):
        if not OPAQUE.fullmatch(reference) or not UUID.fullmatch(request_id):
            raise CartError("PROTOCOL")
        return self.operation(
            self._request(
                "POST",
                "confirm",
                {
                    "purpose": "PREPARE_CART",
                    "source": "TELEGRAM_CALLBACK",
                    "confirmationRef": reference,
                    "requestId": request_id,
                    "callbackId": callback_id,
                },
            )
        )

    def request(self, request_id):
        if not UUID.fullmatch(request_id):
            raise CartError("PROTOCOL")
        return self.operation(self._request("GET", "requests/" + request_id))
