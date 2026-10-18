"""Worker BOT-01: filas locais e recuperação da API; sem IA, OAuth ou compra."""

import hashlib
import threading
import time
from datetime import datetime

from .backend import BackendError
from .conversation import ConversationError
from .conversation_contract import ProtocolError, encode
from .conversation_view import chunks, render
from .outbox import Outbox
from .telegram import TelegramError

NOTICES = {
    "QUEUE_FULL": "A fila de conversa está cheia. Aguarde e envie esta mensagem novamente depois.",
    "EXPIRED": "Uma mensagem aguardou mais de 24 horas sem envio e foi descartada. Envie novamente se ainda fizer sentido.",
    "NO_ACTIVE": "Nenhum processamento ativo foi encontrado para interromper.",
    "LOCAL_CANCELLED": "Mensagem retirada da fila local antes do envio. Nenhum cancelamento remoto foi solicitado.",
    "CANCELLED": "Solicitação de parada local registrada. Isso não cancela nada no iFood.",
    "RESUMED": "Acompanhamento retomado. Uma entrega anterior incerta pode aparecer novamente. Nenhum pedido é reenviado.",
    "STALE_VERSION": "A conversa mudou. O evento antigo não foi alterado ou reaplicado. Envie sua correção novamente sobre o estado atual.",
    "EVENT_CONFLICT": "Este evento já existe com outro conteúdo. Não vou alterar sua identidade; consulte o responsável pelo serviço.",
    "FORBIDDEN": "A conversa não está autorizada para esta conta. Consulte o responsável pelo serviço.",
    "UNAUTHENTICATED": "A autenticação entre bot e API foi recusada. Consulte o responsável pelo serviço.",
    "INVALID_REQUEST": "A API recusou o formato da mensagem. Nenhuma correção automática foi aplicada; consulte o responsável pelo serviço.",
    "LINK_CHANGED": "O vínculo da conta mudou. Confira /ifood antes de enviar uma nova mensagem.",
    "CONTEXT_EXPIRED": "A retomada do grupo expirou após 24 horas. Use /verificar para solicitar uma nova consulta.",
    "NO_CONTEXT": "Não há conversa salva para retomar. Envie uma mensagem para começar; nenhum pedido é enviado.",
    "CONTEXT_LINK_NOT_READY": "Não consegui validar o mesmo vínculo operacional para retomar o grupo. Consulte /ifood e use /verificar quando a conexão estiver pronta.",
    "UNAVAILABLE": "Conversa temporariamente indisponível. Use /retomar para recuperar o mesmo evento, ou consulte /andamento.",
    "PROTOCOL": "Resposta incompatível com o contrato. O acompanhamento está pausado; consulte o responsável pelo serviço.",
    "FAILED": "O processamento terminou sem concluir a solicitação. Envie uma nova correção quando o serviço estiver disponível.",
    "RESULT_UNKNOWN": "Resultado externo desconhecido. Não repita o pedido; é necessária reconciliação. Nenhum envio automático será feito.",
    "CANCEL_UNKNOWN": "A parada local ainda não foi confirmada. Use /retomar para recuperar a mesma solicitação.",
}


def scope_for(config, bot_id):
    origin = config.base_url.rstrip("/").lower()
    return hashlib.sha256(f"{origin}|{bot_id}|{config.organizer_id}".encode()).hexdigest()


def link_fingerprint(status):
    if (
        status.state != "CONNECTED"
        or not status.operational
        or not status.allowed_operations
        or not status.link_id
    ):
        return None
    return hashlib.sha256(status.link_id.encode()).hexdigest()


class Conversations:
    """Adaptador usado só pela thread de recebimento, sem rede de conversa."""

    COMMANDS = frozenset({"/andamento", "/interromper", "/retomar"})

    def __init__(self, box, client):
        self.box, self.client = box, client

    def restore_after_login(self, status, source_key):
        fingerprint = link_fingerprint(status)
        if not fingerprint:
            return None
        return self.box.enqueue_context(source_key, fingerprint)

    def receive(self, update, text_command=None):
        if text_command == "/andamento":
            return self.box.status()
        if text_command in {"/interromper", "/retomar"}:
            command = self.client.prepare_cancel(update, 0, "pending_operation_0000")
            kind = "CANCEL" if text_command == "/interromper" else "RESUME"
        else:
            command, kind = self.client.prepare_text(update, 0), "TEXT"
        # update_id pode reiniciar aleatoriamente após uma semana: messageId também faz parte da chave.
        body = command.to_dict()
        body["eventId"] += "-message-" + body["source"]["messageId"]
        command = self.client.restore(encode(body), command.schema)
        if len(command.serialize()) > 16384:
            raise ValueError("Mensagem excede o limite do backend.")
        self.box.receive(command, update["update_id"], kind=kind)
        return None


class ConversationWorker:
    def __init__(
        self,
        box,
        client,
        telegram,
        organizer_id,
        *,
        clock=time.time,
        stop_event=None,
        link_status=None,
    ):
        self.box, self.client, self.telegram = box, client, telegram
        self.organizer_id, self.clock = organizer_id, clock
        self.stop_event = stop_event or threading.Event()
        self.link_status = link_status

    def _version(self):
        try:
            return self.client.get_snapshot().version
        except ConversationError as error:
            if error.code == "NOT_FOUND":
                return 0
            raise

    def tick(self):
        self.box.expire()
        row = self.box.next()
        if row is None:
            return False
        try:
            state = row["state"]
            if state == "NOTICE":
                self._notice(row)
            elif row["kind"] == "CONTEXT":
                self._context(row)
            elif state == "RECEIVED" or (state == "PAUSED" and row["body"] is not None):
                self.box.prepare(row, self._version())
            elif state in {"PREPARED", "POST_UNKNOWN"} or (
                state == "PAUSED" and not row["operation_id"]
            ):
                self._send(row)
            elif row["operation_id"]:
                self._poll(row)
        except ConversationError as error:
            self._error(row, error)
        except ProtocolError:
            self._error(row, ConversationError("PROTOCOL"))
        return True

    def _context(self, row):
        if self.stop_event.is_set():
            return
        if self.link_status is None:
            raise ConversationError("UNAVAILABLE")
        try:
            before = self.link_status()
            if before.state == "UNAVAILABLE":
                raise ConversationError("UNAVAILABLE")
            if link_fingerprint(before) != row["link_hash"]:
                self.box.save(
                    row["seq"], state="NOTICE", notice="CONTEXT_LINK_NOT_READY", attempts=0
                )
                return
            if self.stop_event.is_set():
                return
            try:
                snapshot = self.client.get_snapshot()
            except ConversationError as error:
                if error.code == "NOT_FOUND":
                    self.box.save(row["seq"], state="NOTICE", notice="NO_CONTEXT", attempts=0)
                    return
                raise
            if self.stop_event.is_set():
                return
            after = self.link_status()
            if after.state == "UNAVAILABLE":
                raise ConversationError("UNAVAILABLE")
            if link_fingerprint(after) != row["link_hash"]:
                self.box.save(
                    row["seq"], state="NOTICE", notice="CONTEXT_LINK_NOT_READY", attempts=0
                )
                return
        except BackendError:
            raise ConversationError("UNAVAILABLE") from None
        self._deliver(row, chunks(render(snapshot, collection_only=True)))

    def _send(self, row):
        # O estado pré-envio sobrevive a queda antes/depois do POST. Recuperar só bytes persistidos.
        command = self.client.restore(
            bytes(row["command"]), "cancel" if row["kind"] == "CANCEL" else "event"
        )
        self.box.save(row["seq"], state="POST_UNKNOWN")
        response = self.client.send(command)
        if row["kind"] == "CANCEL":
            self.box.save(
                row["seq"], state="NOTICE", notice="CANCELLED", command=None, body=None, attempts=0
            )
            return
        document = response.to_dict()
        deadline = datetime.fromisoformat(document["deadlineAt"]).timestamp()
        self.box.save(
            row["seq"],
            state="ACCEPTED",
            operation_id=response.operation_id,
            body=None,
            command=None,
            deadline=deadline,
            attempts=0,
            due=self.clock() + (response.poll_after_ms or 0) / 1000,
        )

    def _poll(self, row):
        operation = self.client.get_operation(row["operation_id"], event_id=row["event_id"])
        if self.stop_event.is_set():
            return
        if not operation.terminal:
            if row["deadline"] and self.clock() > row["deadline"] + 30:
                self.box.save(row["seq"], state="PAUSED", attempts=3)
                self.box.pause_notice(row, "UNAVAILABLE")
                return
            self.box.save(
                row["seq"],
                state="ACCEPTED",
                attempts=0,
                due=self.clock() + operation.poll_after_ms / 1000,
            )
            if self.box.delivered(row["seq"], 0) is None:
                self._deliver(
                    row,
                    [
                        "Estou processando sua mensagem. Você pode continuar escrevendo ou usar /andamento e /interromper."
                    ],
                    final=False,
                )
            return
        if operation.status == "SUCCEEDED":
            # Não reutilizar snapshot histórico da operação: ele pode ter sido substituído/expurgado.
            snapshot = self.client.get_snapshot()
            text = render(snapshot)
        elif operation.status == "RESULT_UNKNOWN":
            self.box.save(row["seq"], state="NOTICE", notice="RESULT_UNKNOWN", attempts=0)
            return
        elif operation.status == "CANCELLED":
            text = NOTICES["LOCAL_CANCELLED"]
        else:
            document = operation.to_dict()
            code = (document.get("error") or {}).get("code")
            text = NOTICES.get(code, NOTICES["FAILED"])
        self._deliver(row, chunks(text))

    def _deliver(self, row, parts, *, final=True):
        # Texto só em memória. Edições de mensagens conhecidas são recuperáveis, envios novos são incertos.
        for index, text in enumerate(parts):
            if self.stop_event.is_set():
                return
            message_id = self.box.delivered(row["seq"], index)
            digest = hashlib.sha256(text.encode()).hexdigest()
            if message_id and self.box.delivery_digest(row["seq"], index) == digest:
                continue
            if row["state"] == "NOTICE":
                next_state = "NOTICE"
            else:
                next_state = "CONTEXT" if row["kind"] == "CONTEXT" else "ACCEPTED"
            self.box.save(row["seq"], state=next_state if message_id else "SENDING")
            try:
                if message_id:
                    self.telegram.call(
                        "editMessageText",
                        {
                            "chat_id": self.organizer_id,
                            "message_id": message_id,
                            "text": text,
                            "reply_markup": {"inline_keyboard": []},
                        },
                    )
                else:
                    response = self.telegram.send(self.organizer_id, text)
                    if (
                        not isinstance(response, dict)
                        or type(response.get("message_id")) is not int
                    ):
                        raise TelegramError()
                    message_id = response["message_id"]
                self.box.record_delivery(row["seq"], index, message_id, digest)
            except TelegramError as error:
                if error.code == 403:
                    self.box.finish(row["seq"])
                elif not message_id and error.code in {0, 500, 502, 503, 504}:
                    self.box.save(row["seq"], state="DELIVERY_UNKNOWN", attempts=3, body=None)
                elif error.code == 400 and message_id:
                    # Pode ser "message is not modified" OU mensagem apagada: sem texto privado no erro.
                    self.box.save(row["seq"], state="DELIVERY_UNKNOWN", attempts=3)
                else:
                    self.box.save(
                        row["seq"],
                        state=next_state,
                        attempts=row["attempts"] + 1,
                        due=self.clock() + max(5, error.retry_after),
                    )
                return
            # Uma chamada Telegram por tick; no seguinte, reconsultar o estado atual antes de continuar.
            self.box.save(row["seq"], state=next_state)
            return
        if final:
            self.box.finish(row["seq"])
        else:
            self.box.save(row["seq"], state="ACCEPTED")

    def _notice(self, row):
        text = NOTICES.get(row["notice"], NOTICES["FAILED"])
        # Avisos também nunca têm texto/resultado copiado da API.
        self._deliver(row, [text])

    def _error(self, row, error):
        with self.box.transaction():
            current = self.box.get(row["seq"])
            if not current or current["state"] in {"DONE", "CANCELLED", "EXPIRED"}:
                return
            paused = self._record_error(current, error)
        if paused:
            self.box.pause_notice(row, "CANCEL_UNKNOWN" if row["kind"] == "CANCEL" else error.code)

    def _record_error(self, row, error):
        if (
            error.code
            in {
                "STALE_VERSION",
                "EVENT_CONFLICT",
                "FORBIDDEN",
                "UNAUTHENTICATED",
                "INVALID_REQUEST",
                "LINK_CHANGED",
            }
            and not error.uncertain
        ):
            self.box.update(
                row["seq"], state="NOTICE", notice=error.code, body=None, command=None, attempts=0
            )
        else:
            attempts = row["attempts"] + 1
            state = "POST_UNKNOWN" if error.uncertain else "PAUSED"
            self.box.update(
                row["seq"],
                state=state,
                attempts=attempts,
                due=self.clock() + min(30, 5 * 2 ** min(attempts - 1, 3)),
            )
            return attempts >= 3
        return False


class ConversationService:
    """Uma thread e um processo; clientes/conexões são construídos na thread proprietária."""

    def __init__(
        self,
        path,
        scope,
        client_factory,
        telegram_factory,
        organizer_id,
        *,
        link_status_factory=None,
    ):
        self.path, self.scope = path, scope
        self.client_factory, self.telegram_factory = client_factory, telegram_factory
        self.organizer_id = organizer_id
        self.link_status_factory = link_status_factory
        self.stop_event = threading.Event()
        self.failed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="conversation-worker", daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        box = None
        try:
            box = Outbox(self.path, self.scope)
            worker = ConversationWorker(
                box,
                self.client_factory(),
                self.telegram_factory(),
                self.organizer_id,
                stop_event=self.stop_event,
                link_status=self.link_status_factory() if self.link_status_factory else None,
            )
            while not self.stop_event.is_set():
                worker.tick()
                self.stop_event.wait(0.25)
        except Exception:  # noqa: BLE001 -- Fronteira da thread: falhar fechado sem traceback privado.
            # Sem traceback/exceção privada; o processo principal verifica esta condição.
            self.failed.set()
        finally:
            if box:
                box.close()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=12)
        if self.thread.is_alive():
            raise ValueError(
                "Worker de conversa não encerrou no prazo; reinicie o processo antes de retomar."
            )
