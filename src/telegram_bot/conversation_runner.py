"""Worker BOT-01: filas locais e recuperação da API; sem IA, OAuth ou compra."""

import hashlib
import threading
import time
from datetime import datetime

from .address_flow import AddressFlow
from .backend import BackendError
from .conversation import ConversationError
from .conversation_contract import ProtocolError, decode, encode
from .conversation_view import chunks, render
from .outbox import Outbox
from .telegram import TelegramError
from .voice import MAX_BYTES, VoiceError, voice_metadata

PROCESSING = "Estou processando sua mensagem e vou trazer a resposta por aqui automaticamente. Você pode continuar escrevendo ou tocar em Interromper."

NOTICES = {
    "ADDRESS_UNAVAILABLE": "A verificação de endereços ainda não está disponível nesta versão da API. Avise a equipe; a coleta do grupo pode continuar.",
    "ADDRESS_SELECTED": "Endereço confirmado para as sugestões. Para trocar, toque em Endereços iFood.",
    "REFERENCE_EXPIRED": "A lista de endereços mudou ou a escolha expirou. Toque em Endereços iFood para conferir novamente.",
    "VOICE_UNKNOWN": "A transcrição foi interrompida e não será repetida automaticamente. Envie o áudio novamente ou escreva a mensagem.",
    "VOICE_FAILED": "Não consegui entender este áudio com segurança ou o limite de voz foi atingido. Tente mais tarde ou escreva a mensagem.",
    "QUEUE_FULL": "A fila de conversa está cheia. Aguarde e envie esta mensagem novamente depois.",
    "EXPIRED": "Uma mensagem aguardou mais de 24 horas sem envio e foi descartada. Envie novamente se ainda fizer sentido.",
    "NO_ACTIVE": "Nenhum processamento ativo foi encontrado para interromper.",
    "LOCAL_CANCELLED": "Mensagem retirada da fila local antes do envio. Nenhum cancelamento remoto foi solicitado.",
    "CANCELLED": "Solicitação de parada local registrada. Isso não cancela nada no iFood.",
    "RESUMED": "Acompanhamento retomado. Se uma resposta já chegou, você pode recebê-la novamente ao recuperar as mensagens pendentes.",
    "STALE_VERSION": "A conversa mudou. O evento antigo não foi alterado ou reaplicado. Envie sua correção novamente sobre o estado atual.",
    "EVENT_CONFLICT": "Este evento já existe com outro conteúdo. Não vou alterar sua identidade; consulte o responsável pelo serviço.",
    "FORBIDDEN": "A conversa não está autorizada para esta conta. Consulte o responsável pelo serviço.",
    "UNAUTHENTICATED": "Não consegui acessar o serviço de compras. Avise a equipe.",
    "INVALID_REQUEST": "A API recusou o formato da mensagem. Nenhuma correção automática foi aplicada; consulte o responsável pelo serviço.",
    "LINK_CHANGED": "O vínculo da conta mudou. Confira Minha conexão antes de enviar uma nova mensagem.",
    "CONTEXT_EXPIRED": "A retomada do grupo expirou após 24 horas. Use Verificar conexão para solicitar uma nova consulta.",
    "NO_CONTEXT": "Não há conversa salva para retomar. Envie uma mensagem para começar.",
    "CONTEXT_LINK_NOT_READY": "Não consegui validar o mesmo vínculo operacional para retomar o grupo. Consulte Minha conexão e use Verificar conexão quando a conexão estiver pronta.",
    "UNAVAILABLE": "Conversa temporariamente indisponível. Use Retomar conversa para recuperar o mesmo evento, ou consulte Acompanhar.",
    "PROTOCOL": "Resposta incompatível com o contrato. O acompanhamento está pausado; consulte o responsável pelo serviço.",
    "FAILED": "O processamento terminou sem concluir a solicitação. Envie uma nova correção quando o serviço estiver disponível.",
    "RESULT_UNKNOWN": "Resultado externo desconhecido. Não repita o pedido; é necessária reconciliação. Nenhum envio automático será feito.",
    "CANCEL_UNKNOWN": "A parada local ainda não foi confirmada. Use Retomar conversa para recuperar a mesma solicitação.",
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

    COMMANDS = frozenset({"/andamento", "/interromper", "/retomar", "/enderecos"})

    def __init__(self, box, client, *, voice_enabled=False):
        self.box, self.client = box, client
        self.voice_enabled = voice_enabled

    def restore_after_login(self, status, source_key):
        fingerprint = link_fingerprint(status)
        if not fingerprint:
            return None
        queued = self.box.enqueue_context(source_key, fingerprint)
        if queued and getattr(self.client, "addresses_supported", False):
            self.box.enqueue_addresses(source_key, fingerprint)
        return queued

    def address_click(self, callback, update_id):
        if not getattr(self.client, "addresses_supported", False):
            return False
        sender, message = callback.get("from"), callback.get("message")
        if not isinstance(sender, dict) or not isinstance(message, dict):
            return False
        chat = message.get("chat")
        if (
            sender.get("is_bot") is not False
            or type(sender.get("id")) is not int
            or sender["id"] != self.client.organizer_id
            or not isinstance(chat, dict)
            or chat.get("type") != "private"
            or type(chat.get("id")) is not int
            or chat["id"] != self.client.organizer_id
        ):
            return False
        return self.box.address_click(callback, update_id, self.client.bot_id)

    def receive(self, update, text_command=None):
        if text_command == "/enderecos":
            queued = self.box.enqueue_addresses("message-" + str(update["update_id"]))
            return (
                "Vou conferir seus endereços cadastrados no iFood."
                if queued
                else NOTICES["QUEUE_FULL"]
            )
        voice = None
        if "voice" in update.get("message", {}):
            if not self.voice_enabled:
                return "Ainda não estou recebendo áudios nesta demo. Por enquanto, escreva sua mensagem."
            try:
                voice = voice_metadata(update["message"])
            except VoiceError:
                return "Envie uma mensagem de voz de até um minuto e 5 MB, ou escreva sua mensagem."
            update = {
                **update,
                "message": {**update["message"], "text": "Áudio aguardando transcrição."},
            }
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
        self.box.receive(command, update["update_id"], kind=kind, voice=voice)
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
        access_allowed=None,
        transcriber=None,
    ):
        self.box, self.client, self.telegram = box, client, telegram
        self.organizer_id, self.clock = organizer_id, clock
        self.stop_event = stop_event or threading.Event()
        self.link_status = link_status
        self.access_allowed = access_allowed
        self.transcriber = transcriber
        self.addresses = AddressFlow(self)

    def _authorized(self):
        return not self.stop_event.is_set() and (
            self.access_allowed is None or self.access_allowed()
        )

    def _version(self):
        try:
            return self.client.get_snapshot().version
        except ConversationError as error:
            if error.code == "NOT_FOUND":
                return 0
            raise

    def tick(self):
        if not self._authorized():
            return False
        self.box.expire()
        row = self.box.next()
        if row is None:
            return False
        if row["state"] not in {"NOTICE", "PAUSED"}:
            self.telegram.typing(self.organizer_id)
        try:
            state = row["state"]
            if state == "DELIVERY_UNKNOWN":
                self.box.save(
                    row["seq"],
                    state="ACCEPTED",
                    attempts=0,
                    delivery_recoveries=row["delivery_recoveries"] + 1,
                )
                row = self.box.get(row["seq"])
                self._poll(row)
                return True
            if state == "NOTICE":
                self._notice(row)
            elif row["kind"].startswith("ADDRESS_"):
                self.addresses.tick(row)
            elif row["kind"] == "CONTEXT":
                self._context(row)
            elif state == "RECEIVED" or (state == "PAUSED" and row["body"] is not None):
                if row["voice"]:
                    self._voice(row)
                else:
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

    def _voice(self, row):
        # Reserva antes da rede: queda/timeout nunca provoca outra transcrição cobrada.
        with self.box.transaction():
            current = self.box.get(row["seq"])
            if current["state"] != "RECEIVED":
                return
            self.box.update(row["seq"], state="TRANSCRIBING")
        try:
            if self.transcriber is None:
                raise VoiceError()
            metadata = decode(bytes(row["voice"]))
            audio = self.telegram.download_voice(metadata["file_id"], MAX_BYTES)
            if not self._authorized():
                self.box.finish(row["seq"])
                return
            self.telegram.typing(self.organizer_id)
            text = self.transcriber.transcribe(audio, metadata["duration"])
            if not self._authorized():
                self.box.finish(row["seq"])
                return
            document = decode(bytes(row["body"]))
            document["input"] = {"kind": "TEXT", "text": text}
            if len(encode(document)) > 16384:
                raise VoiceError()
            self.client.restore(encode(document), "event")
            with self.box.transaction():
                if self.box.get(row["seq"])["state"] != "TRANSCRIBING":
                    return
                self.box.update(row["seq"], state="RECEIVED", body=encode(document), voice=None)
            for part in chunks(
                "Ouvi: "
                + text
                + "\n\nConfira especialmente nomes, alergias e valores. Se algo ficou errado, me corrija por aqui."
            ):
                if not self._authorized():
                    return
                try:
                    self.telegram.send(self.organizer_id, part)
                except TelegramError:
                    break  # Só a prévia falhou; não repetir transcrição nem criar outra intenção.
        except (VoiceError, TelegramError, ProtocolError):
            with self.box.transaction():
                if self.box.get(row["seq"])["state"] == "TRANSCRIBING":
                    self.box.update(
                        row["seq"], state="NOTICE", notice="VOICE_FAILED", body=None, voice=None
                    )

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
        if not self._authorized():
            return
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
                self.box.save(row["seq"], state="PAUSED", attempts=3, notice="UNAVAILABLE")
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
                    [PROCESSING],
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
        self.box.save(row["seq"], notice=operation.status)
        self._deliver(row, chunks(text))

    def _deliver(self, row, parts, *, final=True, markup=None, on_delivery=None):
        # Texto só em memória. Edições de mensagens conhecidas são recuperáveis, envios novos são incertos.
        for index, text in enumerate(parts):
            if not self._authorized():
                return
            message_id = self.box.delivered(row["seq"], index)
            digest = hashlib.sha256(text.encode() + (encode(markup) if markup else b"")).hexdigest()
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
                            "reply_markup": markup or {"inline_keyboard": []},
                        },
                    )
                else:
                    # ReplyKeyboardMarkup torna a mensagem não editável na Bot API.
                    response = self.telegram.send(
                        self.organizer_id, text, markup or {"inline_keyboard": []}
                    )
                    if (
                        not isinstance(response, dict)
                        or type(response.get("message_id")) is not int
                    ):
                        raise TelegramError()
                    message_id = response["message_id"]
                self.box.record_delivery(row["seq"], index, message_id, digest)
                if on_delivery:
                    on_delivery(message_id)
            except TelegramError as error:
                if message_id and error.reason == "NOT_MODIFIED":
                    # Retry da edição cujo ack se perdeu: mesmo ID/conteúdo já aplicado.
                    self.box.record_delivery(row["seq"], index, message_id, digest)
                    if on_delivery:
                        on_delivery(message_id)
                    self.box.save(row["seq"], state=next_state)
                elif error.code == 403:
                    self.box.finish(row["seq"])
                elif message_id and error.reason == "EDIT_UNAVAILABLE":
                    # Recusa explícita: a edição não ocorreu. Substituir apenas esta parte
                    # no próximo tick, reconsultando o resultado atual por GET.
                    with self.box.transaction():
                        self.box.db.execute(
                            "DELETE FROM conversation_delivery WHERE seq=? AND part=?",
                            (row["seq"], index),
                        )
                        self.box.update(
                            row["seq"],
                            state=next_state,
                            attempts=0,
                            due=self.clock() + 1,
                        )
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
                "REFERENCE_EXPIRED",
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
                notice=error.code,
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
        access_allowed_factory=None,
        transcriber_factory=None,
    ):
        self.path, self.scope = path, scope
        self.client_factory, self.telegram_factory = client_factory, telegram_factory
        self.organizer_id = organizer_id
        self.link_status_factory = link_status_factory
        self.access_allowed_factory = access_allowed_factory
        self.transcriber_factory = transcriber_factory
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
                access_allowed=self.access_allowed_factory()
                if self.access_allowed_factory
                else None,
                transcriber=self.transcriber_factory() if self.transcriber_factory else None,
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
