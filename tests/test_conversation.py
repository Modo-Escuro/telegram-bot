"""Conformidade offline: nenhum token real, polling, OAuth ou compra."""

import copy
import hashlib
import io
import json
import unittest
from datetime import UTC, datetime
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from jsonschema import Draft202012Validator, FormatChecker

from telegram_bot.backend import MAX_BODY, BackendConfig
from telegram_bot.conversation import ERRORS, ConversationClient, ConversationError
from telegram_bot.conversation_contract import ProtocolError, decode

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "src/telegram_bot/contracts/v1"
EXAMPLES = json.loads((ROOT / "tests/conversation-examples.json").read_text("utf-8"))
NOW = datetime(2026, 10, 18, tzinfo=UTC)
TOKEN = "synthetic-secret-for-tests-only-xxxxxxxx"


def example(name):
    return copy.deepcopy(next(case["value"] for case in EXAMPLES if case["name"] == name))


def update(number=500):
    return {
        "update_id": number,
        "message": {
            "message_id": 30,
            "from": {"id": 111111111, "is_bot": False},
            "chat": {"type": "private", "id": 111111111},
            "text": example("evento de texto")["input"]["text"],
        },
    }


def callback():
    return {
        "update_id": 501,
        "callback_query": {
            "id": "callback-501",
            "from": {"id": 111111111, "is_bot": False},
            "message": update()["message"],
        },
    }


def headers(content_type="application/json"):
    result = Message()
    result["Content-Type"] = content_type
    return result


class Response(io.BytesIO):
    def __init__(self, body, status=200, *, raw=None, content_type="application/json"):
        super().__init__(json.dumps(body).encode() if raw is None else raw)
        self.status = status
        self.headers = headers(content_type)


class ConversationTests(unittest.TestCase):
    def client(self, body=None, status=202, **response_options):
        opener = Mock()
        opener.open.return_value = Response(
            body or example("operação aceita"), status, **response_options
        )
        client = ConversationClient(
            BackendConfig("https://api.example.test", TOKEN, 111111111),
            900001,
            opener=opener,
            now=lambda: NOW,
        )
        return client, opener

    def test_shared_schemas_examples_and_provenance(self):
        validators = {}
        for path in CONTRACT.glob("*.schema.json"):
            schema = json.loads(path.read_text("utf-8"))
            Draft202012Validator.check_schema(schema)
            validators[path.name.removesuffix(".schema.json")] = Draft202012Validator(
                schema, format_checker=FormatChecker()
            )
        for case in EXAMPLES:
            with self.subTest(case=case["name"]):
                self.assertEqual(validators[case["schema"]].is_valid(case["value"]), case["valid"])
        manifest = json.loads((ROOT / "contracts-provenance.json").read_text("utf-8"))
        for path, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)

    def test_post_exact_contract_headers_timeout_and_immutable_payload(self):
        client, opener = self.client()
        command = client.prepare_text(update(), 0)
        self.assertEqual(command.to_dict(), example("evento de texto"))
        changed = command.to_dict()
        changed["input"]["text"] = "alteração externa"
        operation = client.send(command)
        request = opener.open.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://api.example.test/api/bot/v1/conversations/111111111/events"
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertEqual(request.get_header("X-telegram-user-id"), "111111111")
        self.assertEqual(request.get_header("X-telegram-chat-id"), "111111111")
        self.assertEqual(request.data, command.serialize())
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 15)
        self.assertEqual(operation.status, "ACCEPTED")
        self.assertFalse(operation.terminal)
        self.assertEqual(operation.poll_after_ms, 1000)
        self.assertNotIn("restrição", repr(command))
        self.assertNotIn(TOKEN, repr(client))
        self.assertNotIn("source", repr(operation))

    def test_timeout_then_explicit_restored_replay_preserves_exact_bytes(self):
        client, opener = self.client()
        opener.open.side_effect = [
            TimeoutError("private-provider-data"),
            Response(example("operação aceita"), 200),
        ]
        command = client.prepare_text(update(), 0)
        with self.assertRaises(ConversationError) as caught:
            client.send(command)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(opener.open.call_count, 1)
        restored = client.restore(command.serialize(), command.schema)
        client.send(restored)
        requests = [call.args[0] for call in opener.open.call_args_list]
        self.assertEqual(requests[0].data, requests[1].data)
        self.assertNotIn("private-provider-data", str(caught.exception))

    def test_distinct_equal_text_updates_have_different_event_ids(self):
        client, _ = self.client()
        first, second = (client.prepare_text(update(n), 0).to_dict() for n in (500, 501))
        self.assertNotEqual(first["eventId"], second["eventId"])
        self.assertEqual(first["input"], second["input"])

    def test_invalid_identity_or_update_never_uses_transport(self):
        client, opener = self.client()
        cases = []
        for path, value in (
            ("from", {"id": 222222222}),
            ("chat", {"type": "group", "id": 111111111}),
            ("chat", {"type": "private", "id": 222222222}),
            ("message_id", True),
        ):
            body = update()
            body["message"][path] = value
            cases.append(body)
        cases.extend([{}, {"update_id": True, "message": update()["message"]}])
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ValueError):
                client.prepare_text(body, 0)
        opener.open.assert_not_called()

    def test_invalid_payload_and_version_never_uses_transport(self):
        client, opener = self.client()
        for version in (True, -1, 1.1, 2**53):
            with self.subTest(version=version), self.assertRaises(ProtocolError):
                client.prepare_text(update(), version)
        for text in (None, "", "🍕" * 2001, "\ud800"):
            body = update()
            body["message"]["text"] = text
            with self.subTest(text_length=len(text or "")), self.assertRaises(ProtocolError):
                client.prepare_text(body, 0)
        body["message"]["text"] = "🍕" * 2000
        client.prepare_text(body, 0)
        opener.open.assert_not_called()

    def test_callback_general_actions_cannot_approve_purchase(self):
        client, opener = self.client()
        command = client.prepare_action(callback(), 1, action="REQUEST_REVIEW", action_ref="a" * 24)
        self.assertEqual(command.to_dict()["source"]["kind"], "CALLBACK")
        for action in ("APPROVE_PURCHASE", "UNKNOWN"):
            with self.assertRaises(ProtocolError):
                client.prepare_action(callback(), 1, action=action, action_ref="a" * 24)
        self.assertFalse(hasattr(client, "approve_purchase"))
        opener.open.assert_not_called()

    def test_restore_rejects_other_scope_version_extra_fields_and_approval(self):
        client, opener = self.client()
        for key, value in (
            ("conversationId", "222222222"),
            ("contractVersion", "2.0"),
            ("approvalRef", "a" * 24),
        ):
            body = example("evento de texto")
            body[key] = value
            with self.assertRaises(ProtocolError):
                client.restore(json.dumps(body).encode(), "event")
        body = example("evento de texto")
        body["source"]["botId"] = "900002"
        with self.assertRaises(ProtocolError):
            client.restore(json.dumps(body).encode(), "event")
        with self.assertRaises(ProtocolError):
            client.restore(b"{}", "approval")
        opener.open.assert_not_called()

    def test_get_operation_and_snapshot_use_get_without_body(self):
        body = example("operação concluída com proveniência")
        client, opener = self.client(body, 200)
        operation = client.get_operation(body["operationId"], event_id=body["eventId"])
        self.assertTrue(operation.terminal)
        self.assertEqual(operation.result_version, body["resultVersion"])
        self.assertIsNone(opener.open.call_args.args[0].data)
        snapshot = example("snapshot sem preços confirmados")
        opener.open.return_value = Response(snapshot)
        self.assertEqual(client.get_snapshot().phase, snapshot["phase"])
        self.assertEqual(opener.open.call_args.args[0].method, "GET")

    def test_get_operation_rejects_other_requested_operation_or_event(self):
        for operation_id, event_id in (
            ("x" * 24, "tg-update-500"),
            (example("operação aceita")["operationId"], "wrong-event"),
        ):
            client, _ = self.client(status=200)
            with self.assertRaises(ConversationError):
                client.get_operation(operation_id, event_id=event_id)

    def test_path_injection_rejected_without_transport(self):
        client, opener = self.client()
        for target in ("../purchase-approvals", "x" * 24 + "\n", "https://bad.test", "short"):
            with self.assertRaises(ConversationError):
                client.get_operation(target, event_id="tg-update-500")
        opener.open.assert_not_called()

    def test_cancel_results_keep_own_event_and_do_not_claim_remote_cancellation(self):
        for status, http_status in (
            ("REQUESTED", 202),
            ("CANCELLED", 200),
            ("ALREADY_TERMINAL", 200),
        ):
            result = example("resultado de cancelamento local")
            result.update(eventId="tg-update-502", status=status)
            client, opener = self.client(result, http_status)
            command = client.prepare_cancel(update(502), 1, result["targetOperationId"])
            cancellation = client.send(command)
            self.assertEqual(cancellation.status, status)
            self.assertEqual(cancellation.to_dict()["remoteCancellation"], "NOT_REQUESTED")
            self.assertTrue(
                opener.open.call_args.args[0].full_url.endswith(
                    f"/operations/{result['targetOperationId']}/cancel"
                )
            )

    def test_cancel_wrong_status_scope_target_or_remote_confirmation_rejected(self):
        for key, value in (
            ("eventId", "wrong"),
            ("conversationId", "222222222"),
            ("targetOperationId", "x" * 24),
            ("remoteCancellation", "CONFIRMED"),
        ):
            result = example("resultado de cancelamento local")
            target = result["targetOperationId"]
            result["eventId"] = "tg-update-502"
            result[key] = value
            client, _ = self.client(result, 202)
            with self.assertRaises(ConversationError):
                client.send(client.prepare_cancel(update(502), 1, target))

    def test_all_contract_errors_are_sanitized_and_never_automatically_retried(self):
        for code, (status, recovery, message) in ERRORS.items():
            if code == "PROTOCOL":
                continue
            body = example(f"erro {code}")
            body["error"]["message"] = "private-secret-provider-error"
            client, opener = self.client()
            opener.open.side_effect = HTTPError(
                "https://api.example.test",
                status,
                "private",
                headers(),
                io.BytesIO(json.dumps(body).encode()),
            )
            with self.subTest(code=code), self.assertRaises(ConversationError) as caught:
                client.send(client.prepare_text(update(), 0))
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.recovery, recovery)
            self.assertEqual(str(caught.exception), message)
            self.assertEqual(opener.open.call_count, 1)
            self.assertNotIn("private", str(caught.exception))

    def test_legacy_auth_envelopes_supported_without_echoing_message(self):
        for kind, status, code in (
            ("BOT_AUTH_REQUIRED", 401, "UNAUTHENTICATED"),
            ("ORGANIZER_NOT_ALLOWED", 403, "FORBIDDEN"),
            ("ORGANIZER_REQUIRED", 400, "INVALID_SOURCE"),
            ("BOT_API_NOT_CONFIGURED", 503, "UNAVAILABLE"),
        ):
            client, _ = self.client({"error": {"kind": kind, "message": "private"}}, status)
            with self.assertRaises(ConversationError) as caught:
                client.send(client.prepare_text(update(), 0))
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("private", str(caught.exception))

    def test_unexpected_error_status_recovery_or_shape_rejected(self):
        for status, code, recovery in (
            (200, "STALE_VERSION", "READ_SNAPSHOT"),
            (400, "STALE_VERSION", "READ_SNAPSHOT"),
            (409, "STALE_VERSION", "NONE"),
        ):
            body = example(f"erro {code}")
            body["error"]["recovery"] = recovery
            client, _ = self.client(body, status)
            with self.assertRaises(ConversationError) as caught:
                client.send(client.prepare_text(update(), 0))
            self.assertEqual(caught.exception.code, "PROTOCOL")

    def test_malformed_bounded_json_and_redirect_are_safe_uncertain_post(self):
        for status, raw, content_type in (
            (200, b"<html>private</html>", "text/html"),
            (200, b"{", "application/json"),
            (200, b"{}" + b" " * MAX_BODY, "application/json"),
            (302, b"{}", "application/json"),
            (204, b"", "application/json"),
            (200, b'{"a":1,"a":2}', "application/json"),
            (200, b'{"a":NaN}', "application/json"),
            (200, b"\xff", "application/json"),
        ):
            client, opener = self.client(status=status, raw=raw, content_type=content_type)
            with (
                self.subTest(status=status, size=len(raw)),
                self.assertRaises(ConversationError) as e,
            ):
                client.send(client.prepare_text(update(), 0))
            self.assertEqual(e.exception.code, "PROTOCOL")
            self.assertTrue(e.exception.uncertain)
            self.assertEqual(opener.open.call_count, 1)

    def test_transport_failure_get_is_unavailable_without_mutation_uncertainty(self):
        client, opener = self.client()
        opener.open.side_effect = URLError("private network details")
        with self.assertRaises(ConversationError) as caught:
            client.get_snapshot()
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(caught.exception.code, "UNAVAILABLE")
        self.assertNotIn("private", str(caught.exception))

    def test_operation_scope_provenance_version_and_semantics(self):
        original = example("operação concluída com proveniência")
        changes = [
            lambda b: b.update(conversationId="222222222"),
            lambda b: b.update(eventId="other-event"),
            lambda b: b.update(pollAfterMs=500),
            lambda b: b.update(resultVersion=0),
            lambda b: b.update(snapshot=None),
            lambda b: b.update(deadlineAt="2020-01-01T00:00:00Z"),
            lambda b: b.update(status="FUTURE_STATUS"),
            lambda b: b.update(contractVersion="2.0"),
            lambda b: b["changes"][0]["source"].update(botId="900002"),
            lambda b: b["changes"][0]["source"].update(messageId="99"),
            lambda b: b["snapshot"].update(version=50),
        ]
        for mutate in changes:
            body = copy.deepcopy(original)
            mutate(body)
            client, _ = self.client(body)
            with self.assertRaises(ConversationError):
                client.send(client.prepare_text(update(), 0))

    def test_unknown_failed_and_partial_are_not_promoted_to_success(self):
        for name, status in (
            ("resultado externo desconhecido", "RESULT_UNKNOWN"),
            ("prazo esgotado sem efeito externo", "FAILED"),
            ("resultado parcial exige continuação explícita", "SUCCEEDED"),
        ):
            body = example(name)
            client, _ = self.client(body, 200)
            operation = client.get_operation(body["operationId"], event_id=body["eventId"])
            self.assertEqual(operation.status, status)
            self.assertEqual(operation.completeness, body["completeness"])
            self.assertTrue(operation.terminal)

    def test_snapshot_money_expiry_coverage_and_confirmed_evidence(self):
        base = example("revisão humana sintética")
        review_index = next(i for i, b in enumerate(base["blocks"]) if b["kind"] == "REVIEW")
        mutations = [
            lambda b: b["blocks"][review_index]["price"].update(totalCents=1),
            lambda b: b["blocks"][review_index]["price"].update(totalCents=1.1),
            lambda b: b["blocks"][review_index].update(blockers=["restrição desconhecida"]),
            lambda b: b["blocks"][review_index]["coverage"][0].update(status="BLOCKED"),
            lambda b: b["humanApproval"].update(expectedVersion=999),
            lambda b: b["humanApproval"].update(expiresAt="2020-01-01T00:00:00Z"),
            lambda b: b.update(phase="RESULT_UNKNOWN"),
            lambda b: b["blocks"].append(
                {"kind": "OUTCOME", "stage": "ORDER", "status": "CONFIRMED", "evidenceRef": None}
            ),
        ]
        for mutate in mutations:
            body = copy.deepcopy(base)
            mutate(body)
            client, _ = self.client(body, 200)
            with self.assertRaises(ConversationError):
                client.get_snapshot()

    def test_decoder_rejects_duplicate_keys_non_object_and_nonfinite(self):
        for raw in (b"[]", b'{"a": 1, "a": 2}', b'{"a": Infinity}'):
            with self.assertRaises(ProtocolError):
                decode(raw)

    def test_invalid_timeout_and_bot_identity(self):
        cfg = BackendConfig("https://api.example.test", TOKEN, 111111111)
        for timeout in (0, -1, float("nan"), float("inf"), True, 61):
            with self.assertRaises(ValueError):
                ConversationClient(cfg, 900001, timeout=timeout)
        for bot in (True, 0, -1, 10**20, "900001"):
            with self.assertRaises(ValueError):
                ConversationClient(cfg, bot)

    def test_all_positive_response_examples_with_semantic_checks(self):
        for case in EXAMPLES:
            if not case["valid"] or case["schema"] not in {"snapshot", "operation"}:
                continue
            with self.subTest(case=case["name"]):
                body = case["value"]
                client, _ = self.client(body, 200)
                if case["schema"] == "snapshot":
                    self.assertEqual(client.get_snapshot().version, body["version"])
                else:
                    self.assertEqual(
                        client.get_operation(body["operationId"], event_id=body["eventId"]).status,
                        body["status"],
                    )

    def test_default_urllib_transport_sends_json_and_refuses_redirect(self):
        # Somente loopback: exercício do Request/HTTPError/NoRedirect reais,
        # sem Telegram, API externa ou credenciais reais.
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(
                    (self.path, self.headers, self.rfile.read(int(self.headers["Content-Length"])))
                )
                raw = json.dumps(example("operação aceita")).encode()
                self.send_response(202 if len(requests) == 1 else 302)
                self.send_header("Content-Type", "application/json")
                self.send_header("Location", "/must-not-follow")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *_):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
            thread.start()
            try:
                config = BackendConfig(f"http://127.0.0.1:{server.server_port}", TOKEN, 111111111)
                client = ConversationClient(config, 900001, now=lambda: NOW)
                command = client.prepare_text(update(), 0)
                self.assertEqual(client.send(command).status, "ACCEPTED")
                with self.assertRaises(ConversationError):
                    client.send(command)
            finally:
                server.shutdown()
                thread.join(timeout=2)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0][2], command.serialize())
        self.assertEqual(requests[0][1]["X-Telegram-Chat-Id"], "111111111")
        self.assertTrue(all(path.endswith("/events") for path, _, _ in requests))


if __name__ == "__main__":
    unittest.main()
