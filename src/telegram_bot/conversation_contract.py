"""Contrato v1.0: schemas fixados e regras entre campos, sem efeitos externos."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker


class ProtocolError(Exception):
    def __init__(self):
        super().__init__("Resposta incompatível com o contrato de conversa.")


VALIDATORS = {
    name: Draft202012Validator(
        json.loads(
            files("telegram_bot").joinpath(f"contracts/v1/{name}.schema.json").read_text("utf-8")
        ),
        format_checker=FormatChecker(),
    )
    for name in ("event", "cancel", "cancelResult", "snapshot", "operation", "error")
}


def require(condition: bool) -> None:
    if not condition:
        raise ProtocolError()


def validate(name: str, value: dict) -> None:
    # Não propagar ValidationError: sua representação inclui o payload privado.
    require(VALIDATORS[name].is_valid(value))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def decode(raw: bytes) -> dict:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=lambda _: require(False)
        )
        require(isinstance(value, dict))
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ProtocolError() from None


def encode(value: dict) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
            "utf-8"
        )
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise ProtocolError() from None


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


def check_snapshot(value: dict, now: datetime) -> None:
    for action in value["allowedActions"]:
        require(action["expectedVersion"] == value["version"])
        require(instant(action["expiresAt"]) > now)
    for block in value["blocks"]:
        if block["kind"] == "OUTCOME" and block["status"] == "CONFIRMED":
            require(block["evidenceRef"] is not None)
        if block["kind"] not in {"PROPOSAL", "REVIEW"}:
            continue
        price = block["price"]
        if price["kind"] == "RANGE":
            require(price["minCents"] <= price["maxCents"])
        if price["kind"] == "CONFIRMED":
            total = sum(
                c["amountCents"] * (-1 if c["kind"] == "DISCOUNT" else 1)
                for c in price["components"]
            )
            require(total == price["totalCents"])
    approval = value["humanApproval"]
    if approval:
        require(approval["expectedVersion"] == value["version"])
        review = next(
            (
                b
                for b in value["blocks"]
                if b["kind"] == "REVIEW" and b["reviewRef"] == approval["reviewRef"]
            ),
            None,
        )
        require(value["phase"] == "AWAITING_APPROVAL" and review is not None)
        require(review["price"]["kind"] == "CONFIRMED" and not review["blockers"])
        require(
            bool(review["coverage"]) and all(c["status"] == "COVERED" for c in review["coverage"])
        )
        require(now < instant(approval["expiresAt"]) <= instant(review["price"]["expiresAt"]))
    if value["phase"] in {"SUBMITTING", "RESULT_UNKNOWN"}:
        require(not approval and not value["allowedActions"])


def check_operation(value: dict, bot_id: str, now: datetime) -> None:
    pending = value["status"] in {"ACCEPTED", "RUNNING", "CANCEL_REQUESTED"}
    require((value["pollAfterMs"] is not None) == pending)
    require(instant(value["deadlineAt"]) >= instant(value["createdAt"]))
    if value["status"] == "SUCCEEDED":
        require(
            not value["error"]
            and value["completeness"] != "NONE"
            and value["snapshot"] is not None
            and value["resultVersion"] is not None
        )
    if value["status"] == "FAILED":
        require(value["error"] is not None)
    if value["status"] == "RESULT_UNKNOWN":
        require(bool(value["error"]) and value["error"]["code"] == "RESULT_UNKNOWN")
    if value["resultVersion"] is not None:
        require(value["resultVersion"] >= value["baseVersion"])
    if value["snapshot"]:
        require(
            value["snapshot"]["conversationId"] == value["conversationId"]
            and value["snapshot"]["version"] == value["resultVersion"]
        )
        check_snapshot(value["snapshot"], now)
    for change in value["changes"]:
        require(
            change["eventId"] == value["eventId"]
            and change["source"]["botId"] == bot_id
            and change["source"]["conversationId"] == value["conversationId"]
            and change["baseVersion"] == value["baseVersion"]
            and change["resultVersion"] == value["resultVersion"]
            and change["resultVersion"] > change["baseVersion"]
        )


@dataclass(frozen=True)
class Document:
    """JSON validado, imutável; cópias explícitas são exclusivas do adaptador, nunca do LLM."""

    _raw: bytes = field(repr=False)

    def to_dict(self) -> dict:
        return decode(self._raw)


@dataclass(frozen=True)
class Snapshot(Document):
    version: int
    phase: str


@dataclass(frozen=True)
class Operation(Document):
    operation_id: str = field(repr=False)
    event_id: str = field(repr=False)
    status: str
    base_version: int
    result_version: int | None
    poll_after_ms: int | None
    completeness: str

    @property
    def terminal(self) -> bool:
        return self.status not in {"ACCEPTED", "RUNNING", "CANCEL_REQUESTED"}


@dataclass(frozen=True)
class Cancellation(Document):
    status: str


def utc_now() -> datetime:
    return datetime.now(UTC)
