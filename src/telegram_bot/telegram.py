"""Cliente da Bot API sem registro de URLs (elas contêm o token)."""

import json
import re
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .menu import keyboard


def edit_error_reason(method, code, body):
    description = body.get("description")
    if method != "editMessageText" or code != 400 or not isinstance(description, str):
        return "OTHER"
    if description.startswith("Bad Request: message is not modified"):
        return "NOT_MODIFIED"
    if description in {
        "Bad Request: message can't be edited",
        "Bad Request: message to edit not found",
    }:
        return "EDIT_UNAVAILABLE"
    return "OTHER"


class TelegramError(Exception):
    def __init__(self, code: int = 0, retry_after: int = 0, *, reason="OTHER"):
        self.code = code
        self.retry_after = retry_after
        self.reason = reason if reason in {"NOT_MODIFIED", "EDIT_UNAVAILABLE"} else "OTHER"
        # Nunca incluir corpo remoto, URL ou exceção de transporte.
        super().__init__(f"Falha na comunicação com Telegram (código {code}).")

    @property
    def transient(self):
        return self.code == 0 or self.code == 429 or self.code >= 500


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Telegram:
    METHODS = frozenset(
        {
            "getMe",
            "setMyName",
            "getWebhookInfo",
            "getUpdates",
            "sendMessage",
            "sendChatAction",
            "getFile",
            "deleteMessage",
            "answerCallbackQuery",
            "editMessageReplyMarkup",
            "editMessageText",
        }
    )

    def __init__(self, token, opener=None, *, timeout=40, cart_enabled=False):
        self._base = f"https://api.telegram.org/bot{token}/"
        self._opener = opener or build_opener(NoRedirect())
        self._timeout = timeout
        self._typing_at = {}
        self.cart_enabled = cart_enabled

    def typing(self, chat_id):
        """Sinal nativo e efêmero; falha visual nunca interrompe a conversa."""
        now = time.monotonic()
        if now - self._typing_at.get(chat_id, -10) < 4:
            return
        self._typing_at = {k: v for k, v in self._typing_at.items() if now - v < 4}
        self._typing_at[chat_id] = now
        try:
            self.call("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=1)
        except TelegramError:
            pass

    def configure_name(self, me):
        if me.get("first_name") == "Ailo":
            return
        try:
            self.call("setMyName", {"name": "Ailo"}, timeout=3)
        except TelegramError:
            pass  # Nome visual não pode impedir o serviço; pode ser ajustado no BotFather.

    def call(self, method, payload=None, *, timeout=None):
        if method not in self.METHODS:
            raise ValueError("Método Telegram não implementado.")
        request = Request(
            self._base + method,
            data=json.dumps(payload or {}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(
                request, timeout=self._timeout if timeout is None else timeout
            ) as response:
                body = json.load(response)
        except HTTPError as exc:
            code = exc.code
            retry_after = 0
            reason = "OTHER"
            try:
                body = json.load(exc)
                retry_after = int(body.get("parameters", {}).get("retry_after", 0))
                reason = edit_error_reason(method, code, body)
            except (ValueError, TypeError, AttributeError):
                pass
            finally:
                exc.close()
            raise TelegramError(code, max(0, retry_after), reason=reason) from None
        except (URLError, OSError, ValueError, HTTPException):
            raise TelegramError() from None
        if not isinstance(body, dict):
            raise TelegramError()
        if body.get("ok") is not True:
            code = body.get("error_code", 0)
            params = body.get("parameters") or {}
            retry_after = params.get("retry_after", 0) if isinstance(params, dict) else 0
            raise TelegramError(
                code if type(code) is int else 0,
                retry_after if type(retry_after) is int and retry_after > 0 else 0,
                reason=edit_error_reason(method, code, body),
            )
        return body.get("result")

    def updates(self, offset, *, timeout=25):
        payload = {
            "timeout": timeout,
            "limit": 100,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = self.call("getUpdates", payload)
        if not isinstance(result, list):
            raise TelegramError()
        if any(
            not isinstance(u, dict) or type(u.get("update_id")) is not int or u["update_id"] < 0
            for u in result
        ):
            raise TelegramError()
        return result

    def download_voice(self, file_id, limit):
        info = self.call("getFile", {"file_id": file_id}, timeout=5)
        path = info.get("file_path") if isinstance(info, dict) else None
        if (
            not isinstance(path, str)
            or not re.fullmatch(r"[A-Za-z0-9_/-]+\.[A-Za-z0-9]+", path)
            or path.startswith("/")
            or ".." in path
        ):
            raise TelegramError()
        url = self._base.replace("/bot", "/file/bot", 1) + path
        try:
            with self._opener.open(Request(url), timeout=5) as response:
                data = response.read(limit + 1)
            if not 0 < len(data) <= limit:
                raise TelegramError()
            return data
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise TelegramError(code) from None
        except (URLError, OSError, HTTPException, ValueError):
            raise TelegramError() from None

    def send(self, chat_id, text, markup=None):
        payload = {"chat_id": chat_id, "text": text}
        payload["reply_markup"] = markup if markup is not None else keyboard(cart=self.cart_enabled)
        return self.call("sendMessage", payload)

    def check(self):
        me = self.call("getMe")
        if not isinstance(me, dict) or me.get("is_bot") is not True:
            raise TelegramError()
        if type(me.get("id")) is not int or not isinstance(me.get("username"), str):
            raise TelegramError()
        webhook = self.call("getWebhookInfo")
        if not isinstance(webhook, dict) or "url" not in webhook:
            raise TelegramError()
        if webhook["url"]:
            raise ValueError(
                "Existe webhook ativo. Desative-o antes do long polling; nada foi alterado."
            )
        return me
