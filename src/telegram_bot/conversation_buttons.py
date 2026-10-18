"""Referências técnicas de navegação; nenhum snapshot ou texto de catálogo persistido."""

import hashlib
import re
from datetime import datetime


def offered(snapshot, *, cart=False):
    result = []
    for action in snapshot.to_dict()["allowedActions"]:
        code = action["actionRef"].split("_", 1)[0]
        label = None
        if re.fullmatch(r"choose[1-4]", code) and action["kind"] == "SELECT_PROPOSAL":
            label = "Escolher opção " + code[-1]
        elif action["kind"] == "EDIT_CONTEXT":
            label = {
                "search": "Mudar busca",
                "more": "Ver outras",
                "clear": "Esvaziar carrinho",
                "none": "Não tenho restrições",
            }.get(code)
        elif code == "review" and action["kind"] == "REQUEST_REVIEW" and cart:
            label = "Revisar carrinho"
        if label:
            result.append((label, action))
    return result


def markup(options):
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": "cv:" + action["actionRef"]}]
            for label, action in options
        ]
    }


def bind(box, message_id, bot_id, options):
    with box.db:
        box.db.execute(
            "DELETE FROM conversation_buttons WHERE scope=? AND expires<=?",
            (box.scope, box.clock()),
        )
        for _, action in options:
            box.db.execute(
                "DELETE FROM conversation_buttons WHERE scope=? AND version<>?",
                (box.scope, action["expectedVersion"]),
            )
            box.db.execute(
                "INSERT OR REPLACE INTO conversation_buttons VALUES(?,?,?,?,?,?,?)",
                (
                    box.scope,
                    hashlib.sha256(action["actionRef"].encode()).hexdigest(),
                    message_id,
                    bot_id,
                    action["kind"],
                    action["expectedVersion"],
                    datetime.fromisoformat(action["expiresAt"]).timestamp(),
                ),
            )


def resolve(box, callback, bot_id):
    message, data = callback.get("message", {}), callback.get("data", "")
    if not isinstance(message, dict) or not isinstance(message.get("from"), dict):
        return None
    source = message.get("from", {})
    if (
        not isinstance(data, str)
        or not re.fullmatch(r"cv:[A-Za-z0-9_-]{16,60}", data)
        or source.get("is_bot") is not True
        or type(source.get("id")) is not int
        or source["id"] != bot_id
        or type(message.get("message_id")) is not int
        or message.get("forward_origin")
    ):
        return None
    return box.db.execute(
        "SELECT kind,version FROM conversation_buttons WHERE scope=? AND ref_hash=? AND message_id=? AND bot_id=? AND expires>?",
        (
            box.scope,
            hashlib.sha256(data[3:].encode()).hexdigest(),
            message.get("message_id"),
            bot_id,
            box.clock(),
        ),
    ).fetchone()
