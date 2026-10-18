"""Cliente da Bot API sem registro de URLs (elas contêm o token)."""

import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .menu import keyboard


class TelegramError(Exception):
    def __init__(self, code: int = 0, retry_after: int = 0):
        self.code = code
        self.retry_after = retry_after
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
            "getWebhookInfo",
            "getUpdates",
            "sendMessage",
            "deleteMessage",
            "answerCallbackQuery",
            "editMessageReplyMarkup",
            "editMessageText",
        }
    )

    def __init__(self, token, opener=None, *, timeout=40):
        self._base = f"https://api.telegram.org/bot{token}/"
        self._opener = opener or build_opener(NoRedirect())
        self._timeout = timeout

    def call(self, method, payload=None):
        if method not in self.METHODS:
            raise ValueError("Método Telegram não implementado.")
        request = Request(
            self._base + method,
            data=json.dumps(payload or {}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                body = json.load(response)
        except HTTPError as exc:
            code = exc.code
            retry_after = 0
            try:
                body = json.load(exc)
                retry_after = int(body.get("parameters", {}).get("retry_after", 0))
            except (ValueError, TypeError, AttributeError):
                pass
            finally:
                exc.close()
            raise TelegramError(code, max(0, retry_after)) from None
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

    def send(self, chat_id, text, markup=None):
        payload = {"chat_id": chat_id, "text": text}
        payload["reply_markup"] = markup if markup is not None else keyboard()
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
