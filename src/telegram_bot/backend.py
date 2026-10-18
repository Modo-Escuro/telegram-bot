"""Contrato HTTP de login do api-backend; sem OAuth nem credenciais iFood no bot."""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from http.client import HTTPException
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener

from .telegram import NoRedirect

STATES = frozenset(
    {
        "DISCONNECTED",
        "AWAITING_AUTHORIZATION",
        "AWAITING_CONFIRMATION",
        "CONNECTED",
        "RECONNECT_REQUIRED",
        "UNAVAILABLE",
    }
)
OPERATIONS = frozenset({"ADDRESSES_READ", "OFFERS_EVALUATE"})
OPAQUE = re.compile(r"[A-Za-z0-9_-]{10,100}")
ERROR_KINDS = frozenset(
    {
        "BOT_API_NOT_CONFIGURED",
        "BOT_AUTH_REQUIRED",
        "ORGANIZER_REQUIRED",
        "ORGANIZER_NOT_ALLOWED",
        "IFOOD_CLIENT_NOT_CONFIGURED",
        "ATTEMPT_NOT_FOUND",
        "AUTHORIZATION_PENDING",
        "ATTEMPT_LOCKED",
        "ATTEMPT_EXPIRED",
        "ATTEMPT_USED",
        "INVALID_VERIFICATION_CODE",
        "CONFIRMATION_NOT_FOUND",
        "CONFIRMATION_EXPIRED",
        "CONFIRMATION_INVALID",
        "ALREADY_CONFIRMED",
        "IFOOD_LINK_REQUIRED",
        "IFOOD_UNAVAILABLE",
        "IFOOD_RECONNECT_REQUIRED",
        "IFOOD_SCOPE_MISSING",
    }
)
PREFIX = "/api/bot/ifood/"
MAX_BODY = 1_048_576


def loopback(host):
    if host == "localhost":
        return True
    try:
        return ip_address(host or "").is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class BackendConfig:
    base_url: str
    token: str = field(repr=False)
    organizer_id: int

    def __post_init__(self):
        try:
            url = urlsplit(self.base_url)
            port = url.port
        except ValueError:
            raise ValueError("BACKEND_BASE_URL inválida.") from None
        if (
            not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
            or any(c.isspace() for c in self.base_url)
            or url.scheme not in {"http", "https"}
            or (url.scheme == "http" and not loopback(url.hostname))
            or (port is not None and port < 1)
        ):
            raise ValueError("Use BACKEND_BASE_URL como origem HTTPS ou HTTP de localhost.")
        if not re.fullmatch(r"[!-~]{32,512}", self.token):
            raise ValueError("BACKEND_API_TOKEN deve ter 32 a 512 caracteres ASCII sem espaços.")
        if type(self.organizer_id) is not int or self.organizer_id <= 0:
            raise ValueError("Organizador do backend inválido.")

    @classmethod
    def from_env(cls, organizer_id):
        base = os.getenv("BACKEND_BASE_URL", "").strip()
        token = os.getenv("BACKEND_API_TOKEN", "").strip()
        if not base and not token:
            return None
        if not base or not token:
            raise ValueError("Configure BACKEND_BASE_URL e BACKEND_API_TOKEN juntos.")
        return cls(base.rstrip("/"), token, organizer_id)


class BackendError(Exception):
    def __init__(self, kind="UNAVAILABLE", *, uncertain=False):
        self.kind = kind if kind in ERROR_KINDS | {"UNAVAILABLE", "PROTOCOL"} else "UNAVAILABLE"
        self.uncertain = uncertain
        super().__init__("Falha na comunicação com a API de conexão iFood.")


@dataclass(frozen=True)
class LinkStatus:
    state: str
    operational: bool
    allowed_operations: tuple[str, ...]
    attempt_id: str | None
    attempt_status: str | None
    link_id: str | None
    confirmation_id: str | None = None
    identity: dict | None = field(default=None, repr=False)
    attempt_expires_at: float | None = None

    @classmethod
    def parse(cls, body):
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("state"), str)
            or body["state"] not in STATES
        ):
            raise BackendError("PROTOCOL")
        operations = body.get("allowedOperations")
        if (
            type(body.get("operational")) is not bool
            or not isinstance(operations, list)
            or any(not isinstance(op, str) or op not in OPERATIONS for op in operations)
        ):
            raise BackendError("PROTOCOL")
        attempt = body.get("attempt")
        attempt_id = attempt_status = None
        if attempt is not None:
            if not isinstance(attempt, dict):
                raise BackendError("PROTOCOL")
            attempt_id, attempt_status = attempt.get("attemptId"), attempt.get("status")
            if (
                not isinstance(attempt_id, str)
                or not OPAQUE.fullmatch(attempt_id)
                or not isinstance(attempt_status, str)
                or attempt_status not in {"PENDING_AUTHORIZATION", "PENDING_CONFIRMATION"}
            ):
                raise BackendError("PROTOCOL")
        confirmation_id = attempt.get("confirmationId") if attempt else None
        if confirmation_id is not None and (
            not isinstance(confirmation_id, str)
            or not OPAQUE.fullmatch(confirmation_id)
            or len(confirmation_id.encode("utf-8")) > 60
        ):
            raise BackendError("PROTOCOL")
        identity = attempt.get("accountIdentity") if attempt else None
        if identity is not None and not isinstance(identity, dict):
            raise BackendError("PROTOCOL")
        link_id = body.get("linkId")
        if link_id is not None and (not isinstance(link_id, str) or not OPAQUE.fullmatch(link_id)):
            raise BackendError("PROTOCOL")
        if body["operational"] and not link_id:
            raise BackendError("PROTOCOL")
        expires_at = None
        if attempt and "expiresAt" in attempt:
            try:
                expires = datetime.fromisoformat(attempt["expiresAt"])
                if expires.tzinfo is None:
                    raise ValueError
                expires_at = expires.timestamp()
            except (ValueError, TypeError, AttributeError, OverflowError):
                raise BackendError("PROTOCOL") from None
        return cls(
            body["state"],
            body["operational"],
            tuple(operations),
            attempt_id,
            attempt_status,
            link_id,
            confirmation_id,
            identity,
            expires_at,
        )


class Backend:
    def __init__(self, config, opener=None):
        self.config = config
        self._opener = opener or build_opener(NoRedirect())

    def _request(self, method, action, payload=None, *, timeout=50):
        if (method, action) not in {
            ("GET", "status"),
            ("POST", "connect"),
            ("POST", "confirm"),
            ("POST", "verify"),
            ("POST", "cancel"),
            ("DELETE", "link"),
        }:
            raise ValueError("Operação de conexão não implementada.")
        request = Request(
            self.config.base_url.rstrip("/") + PREFIX + action,
            data=None if method == "GET" else json.dumps(payload or {}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.token}",
                "X-Telegram-User-Id": str(self.config.organizer_id),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise BackendError("PROTOCOL", uncertain=method != "GET")
            body = json.loads(raw)
        except HTTPError as exc:
            kind = "UNAVAILABLE"
            try:
                raw = exc.read(MAX_BODY + 1)
                data = json.loads(raw) if len(raw) <= MAX_BODY else {}
                error = data.get("error", {}) if isinstance(data, dict) else {}
                candidate = error.get("kind") if isinstance(error, dict) else None
                if isinstance(candidate, str) and candidate in ERROR_KINDS:
                    kind = candidate
            except (ValueError, OSError, HTTPException):
                pass
            finally:
                exc.close()
            raise BackendError(kind, uncertain=method != "GET" and exc.code >= 500) from None
        except (URLError, OSError, HTTPException):
            raise BackendError(uncertain=method != "GET") from None
        except (ValueError, UnicodeError):
            raise BackendError("PROTOCOL", uncertain=method != "GET") from None
        if not isinstance(body, dict):
            raise BackendError("PROTOCOL", uncertain=method != "GET")
        return body

    def status(self, *, timeout=50):
        return LinkStatus.parse(self._request("GET", "status", timeout=timeout))

    def connect(self):
        body = self._request("POST", "connect")
        status = LinkStatus.parse(body)
        url = body.get("authorizationUrl")
        if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() for c in url):
            raise BackendError("PROTOCOL", uncertain=True)
        try:
            parts, base = urlsplit(url), urlsplit(self.config.base_url)
            query = parse_qs(parts.query, strict_parsing=True)
            valid = (
                (parts.scheme, parts.netloc.lower()) == (base.scheme, base.netloc.lower())
                and parts.path == "/auth/ifood/start"
                and not parts.fragment
                and set(query) == {"a", "t"}
                and len(query["a"]) == len(query["t"]) == 1
                and query["a"][0] == status.attempt_id
                and OPAQUE.fullmatch(query["t"][0])
                and status.state == "AWAITING_AUTHORIZATION"
                and status.attempt_status == "PENDING_AUTHORIZATION"
            )
        except ValueError:
            valid = False
        if not valid:
            raise BackendError("PROTOCOL", uncertain=True)
        return status, url

    def confirm(self, confirmation_id):
        return LinkStatus.parse(
            self._request(
                "POST",
                "confirm",
                {"confirmationId": confirmation_id},
            )
        )

    def verify(self):
        return LinkStatus.parse(self._request("POST", "verify"))

    def cancel(self):
        body = self._request("POST", "cancel")
        if type(body.get("cancelled")) is not bool:
            raise BackendError("PROTOCOL", uncertain=True)
        return LinkStatus.parse(body), body["cancelled"]

    def disconnect(self):
        body = self._request("DELETE", "link")
        if (
            type(body.get("removed")) is not bool
            or body.get("providerRevocation") != "NOT_ATTEMPTED"
        ):
            raise BackendError("PROTOCOL", uncertain=True)
        return LinkStatus.parse(body), body["removed"]
