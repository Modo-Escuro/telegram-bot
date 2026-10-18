"""Fila local da BOT-01. Cada thread usa sua conexão; nunca guarda snapshots/tokens."""

import hashlib
import sqlite3
import time
from contextlib import contextmanager

from .conversation_contract import ProtocolError, decode, encode

DAY = 86400
TERMINAL = ("DONE", "CANCELLED", "EXPIRED")


class Outbox:
    def __init__(self, path, scope, *, clock=time.time, capacity=10):
        self.clock, self.scope, self.capacity = clock, scope, capacity
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS conversation_outbox ("
            "seq INTEGER PRIMARY KEY, scope TEXT NOT NULL, event_id TEXT NOT NULL, "
            "digest TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL, "
            "body BLOB, command BLOB, operation_id TEXT, target INTEGER, "
            "message_id INTEGER, created REAL NOT NULL, due REAL NOT NULL, "
            "deadline REAL, attempts INTEGER NOT NULL DEFAULT 0, notice TEXT, "
            "UNIQUE(scope,event_id))"
        )
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(conversation_outbox)")}
        if "link_hash" not in columns:
            self.db.execute("ALTER TABLE conversation_outbox ADD COLUMN link_hash TEXT")
        if "voice" not in columns:
            self.db.execute("ALTER TABLE conversation_outbox ADD COLUMN voice BLOB")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS conversation_delivery ("
            "seq INTEGER NOT NULL, part INTEGER NOT NULL, message_id INTEGER NOT NULL, digest TEXT NOT NULL, "
            "PRIMARY KEY(seq,part))"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS address_buttons (scope TEXT NOT NULL, ref_hash TEXT NOT NULL, "
            "message_id INTEGER NOT NULL, bot_id INTEGER NOT NULL, expires REAL NOT NULL, "
            "PRIMARY KEY(scope,ref_hash,message_id))"
        )
        self.db.commit()
        # Crash entre envio Telegram e gravação do message_id: entrega possivelmente ocorreu.
        with self.db:
            self.db.execute(
                "UPDATE conversation_outbox SET state='NOTICE',notice='VOICE_UNKNOWN',voice=NULL,body=NULL,attempts=0 WHERE scope=? AND state='TRANSCRIBING'",
                (scope,),
            )
            self.db.execute(
                "UPDATE conversation_outbox SET state='DELIVERY_UNKNOWN' "
                "WHERE scope=? AND state='SENDING'",
                (scope,),
            )

    def close(self):
        self.db.close()

    def enqueue_context(self, source_key, link_hash):
        """Retomada só de leitura; sem update, linkId, identidade ou resultado persistidos."""
        event_id = "login-context-" + source_key
        digest = hashlib.sha256(link_hash.encode()).hexdigest()
        with self.transaction():
            previous = self.db.execute(
                "SELECT digest FROM conversation_outbox WHERE scope=? AND event_id=?",
                (self.scope, event_id),
            ).fetchone()
            if previous:
                # Replay depois de troca de conta não reescreve a solicitação antiga.
                return previous[0] == digest
            # Só libera GET de operação conhecida, nunca POST ou entrega incerta.
            self.db.execute(
                "UPDATE conversation_outbox SET attempts=0,due=?,state='ACCEPTED' "
                "WHERE scope=? AND kind='TEXT' AND operation_id IS NOT NULL "
                "AND state='PAUSED' AND notice='UNAVAILABLE'",
                (self.clock(), self.scope),
            )
            count = self.db.execute(
                "SELECT count(*),sum(state NOT IN ('DONE','CANCELLED','EXPIRED')) "
                "FROM conversation_outbox WHERE scope=?",
                (self.scope,),
            ).fetchone()
            if count[0] >= 10000 or (count[1] or 0) >= self.capacity:
                return False
            self.db.execute(
                "INSERT INTO conversation_outbox "
                "(scope,event_id,digest,kind,state,created,due,link_hash) "
                "VALUES (?,?,?,'CONTEXT','CONTEXT',?,?,?)",
                (self.scope, event_id, digest, self.clock(), self.clock(), link_hash),
            )
        return True

    def enqueue_addresses(self, source_key, link_hash=None):
        with self.transaction():
            event_id = "address-review-" + source_key
            existing = self.db.execute(
                "SELECT 1 FROM conversation_outbox WHERE scope=? AND event_id=?",
                (self.scope, event_id),
            ).fetchone()
            if existing:
                return True
            count = self.db.execute(
                "SELECT count(*) FROM conversation_outbox WHERE scope=? AND state NOT IN ('DONE','CANCELLED','EXPIRED')",
                (self.scope,),
            ).fetchone()[0]
            if count >= self.capacity:
                return False
            records = self.db.execute(
                "SELECT count(*) FROM conversation_outbox WHERE scope=?", (self.scope,)
            ).fetchone()[0]
            if records >= 10000:
                return False
            self.db.execute(
                "INSERT INTO conversation_outbox(scope,event_id,digest,kind,state,created,due,link_hash) "
                "VALUES(?,?,?,'ADDRESS_REVIEW','RECEIVED',?,?,?)",
                (
                    self.scope,
                    event_id,
                    "technical-address-review",
                    self.clock(),
                    self.clock(),
                    link_hash,
                ),
            )
        return True

    def bind_addresses(self, message_id, bot_id, options):
        from datetime import datetime

        with self.db:
            for option in options:
                expires = datetime.fromisoformat(option["expiresAt"]).timestamp()
                if not self.clock() < expires <= self.clock() + 301:
                    raise ProtocolError()
                self.db.execute(
                    "INSERT OR REPLACE INTO address_buttons VALUES(?,?,?,?,?)",
                    (
                        self.scope,
                        hashlib.sha256(option["choiceRef"].encode()).hexdigest(),
                        message_id,
                        bot_id,
                        expires,
                    ),
                )

    def address_click(self, callback, update_id, bot_id):
        """Referência só é enfileirada após origem e mensagem humanas verificadas."""
        sender, message = callback.get("from"), callback.get("message")
        if not isinstance(sender, dict) or not isinstance(message, dict):
            return False
        data, callback_id = callback.get("data"), callback.get("id")
        if (
            not isinstance(data, str)
            or not data.startswith("ifa:")
            or len(data) != 36
            or not isinstance(callback_id, str)
            or not 0 < len(callback_id) <= 128
            or type(message.get("message_id")) is not int
            or message["message_id"] <= 0
        ):
            return False
        source = message.get("from")
        reference = data[4:]
        if (
            not isinstance(source, dict)
            or source.get("is_bot") is not True
            or type(source.get("id")) is not int
            or source["id"] != bot_id
            or message.get("forward_origin")
            or not isinstance(reference, str)
        ):
            return False
        digest = hashlib.sha256(reference.encode()).hexdigest()
        with self.transaction():
            binding = self.db.execute(
                "SELECT 1 FROM address_buttons WHERE scope=? AND ref_hash=? AND message_id=? AND bot_id=? AND expires>?",
                (
                    self.scope,
                    digest,
                    message["message_id"],
                    bot_id,
                    self.clock(),
                ),
            ).fetchone()
            if not binding:
                return False
            event_id = "address-choice-" + hashlib.sha256(callback["id"].encode()).hexdigest()
            raw = encode({"choiceRef": reference})
            self.db.execute(
                "INSERT OR IGNORE INTO conversation_outbox(scope,event_id,digest,kind,state,body,created,due) VALUES(?,?,?,'ADDRESS_SELECT','RECEIVED',?,?,?)",
                (
                    self.scope,
                    event_id,
                    hashlib.sha256(raw).hexdigest(),
                    raw,
                    self.clock(),
                    self.clock(),
                ),
            )
            self.db.execute("DELETE FROM address_buttons WHERE scope=?", (self.scope,))
            self.db.execute(
                "INSERT INTO cursor VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET offset=MAX(cursor.offset,excluded.offset),updated=excluded.updated",
                (update_id + 1, self.clock()),
            )
        return True

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def receive(self, command, update_id, *, kind="TEXT", voice=None):
        """Mensagem/controle e cursor na MESMA transação; nenhuma rede antes do commit."""
        body = command.serialize()
        document = command.to_dict()
        event_id = document["eventId"]
        digest = hashlib.sha256(body + (encode(voice) if voice else b"")).hexdigest()
        now = self.clock()
        with self.transaction():
            previous = self.db.execute(
                "SELECT * FROM conversation_outbox WHERE scope=? AND event_id=?",
                (self.scope, event_id),
            ).fetchone()
            if previous and previous["digest"] != digest:
                raise ProtocolError()
            if not previous:
                count = self.db.execute(
                    "SELECT count(*) FROM conversation_outbox WHERE scope=? "
                    "AND state NOT IN ('DONE','CANCELLED','EXPIRED')",
                    (self.scope,),
                ).fetchone()[0]
                # Limite também de metadados: não confirmar recebimento sem guardar a recusa.
                records = self.db.execute(
                    "SELECT count(*) FROM conversation_outbox WHERE scope=?", (self.scope,)
                ).fetchone()[0]
                if records >= 10000:
                    raise ValueError(
                        "Limite local atingido; manutenção do armazenamento necessária."
                    )
                state, notice = "RECEIVED", None
                target = None
                if kind == "CANCEL":
                    active = self.active()
                    target = active["seq"] if active else None
                    if not active:
                        state, notice = "NOTICE", "NO_ACTIVE"
                    elif active["state"] in {"RECEIVED", "TRANSCRIBING"}:
                        self.update(
                            active["seq"], state="CANCELLED", body=None, command=None, voice=None
                        )
                        state, notice = "NOTICE", "LOCAL_CANCELLED"
                elif kind == "RESUME":
                    self.db.execute(
                        "DELETE FROM conversation_delivery WHERE seq IN "
                        "(SELECT seq FROM conversation_outbox WHERE scope=? AND state='DELIVERY_UNKNOWN')",
                        (self.scope,),
                    )
                    self.db.execute(
                        "UPDATE conversation_outbox SET attempts=0,due=?,state=CASE "
                        "WHEN state='DELIVERY_UNKNOWN' THEN CASE WHEN operation_id IS NULL "
                        "THEN CASE WHEN kind='CONTEXT' THEN 'CONTEXT' ELSE 'NOTICE' END "
                        "ELSE 'ACCEPTED' END ELSE state END "
                        "WHERE scope=? AND state IN ('PAUSED','POST_UNKNOWN','DELIVERY_UNKNOWN')",
                        (now, self.scope),
                    )
                    state, notice = "NOTICE", "RESUMED"
                elif count >= self.capacity:
                    state, notice = "NOTICE", "QUEUE_FULL"
                self.db.execute(
                    "INSERT INTO conversation_outbox "
                    "(scope,event_id,digest,kind,state,body,target,created,due,notice) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        self.scope,
                        event_id,
                        digest,
                        kind,
                        state,
                        body if state == "RECEIVED" else None,
                        target,
                        now,
                        now,
                        notice,
                    ),
                )
                if voice and state == "RECEIVED":
                    self.db.execute(
                        "UPDATE conversation_outbox SET voice=? WHERE scope=? AND event_id=?",
                        (encode(voice), self.scope, event_id),
                    )
            self.db.execute(
                "INSERT INTO cursor VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET "
                "offset=MAX(cursor.offset,excluded.offset),updated=excluded.updated",
                (update_id + 1, now),
            )

    def active(self):
        return self.db.execute(
            "SELECT * FROM conversation_outbox WHERE scope=? AND kind='TEXT' "
            "AND state NOT IN ('DONE','CANCELLED','EXPIRED') ORDER BY seq LIMIT 1",
            (self.scope,),
        ).fetchone()

    def next(self):
        now = self.clock()
        # Cancelamento com alvo ainda sem aceite espera a recuperação idempotente do alvo.
        control = self.db.execute(
            "SELECT o.* FROM conversation_outbox o LEFT JOIN conversation_outbox t ON t.seq=o.target "
            "WHERE o.scope=? AND (o.kind<>'TEXT' OR o.state='NOTICE') AND o.state NOT IN ('DONE','EXPIRED','CANCELLED') "
            "AND o.state<>'DELIVERY_UNKNOWN' AND o.attempts<3 "
            "AND o.due<=? AND (o.kind<>'CANCEL' OR o.state='NOTICE' OR t.operation_id IS NOT NULL "
            "OR t.state IN ('DONE','EXPIRED','CANCELLED')) ORDER BY o.seq LIMIT 1",
            (self.scope, now),
        ).fetchone()
        if control:
            return control
        active = self.active()
        return (
            active
            if active
            and active["due"] <= now
            and active["attempts"] < 3
            and active["state"] != "DELIVERY_UNKNOWN"
            else None
        )

    def get(self, seq):
        return self.db.execute(
            "SELECT * FROM conversation_outbox WHERE seq=? AND scope=?", (seq, self.scope)
        ).fetchone()

    def update(self, seq, **fields):
        allowed = {
            "state",
            "body",
            "command",
            "operation_id",
            "message_id",
            "due",
            "deadline",
            "attempts",
            "notice",
            "voice",
        }
        if not fields or not fields.keys() <= allowed:
            raise ValueError("Transição local inválida.")
        self.db.execute(
            "UPDATE conversation_outbox SET "
            + ",".join(f"{key}=?" for key in fields)
            + " WHERE seq=? AND scope=?",
            (*fields.values(), seq, self.scope),
        )

    def save(self, seq, **fields):
        with self.db:
            self.update(seq, **fields)

    def prepare(self, row, version):
        # A consulta HTTP de versão pode ter coincidido com /interromper na outra conexão.
        with self.transaction():
            current = self.get(row["seq"])
            if (
                not current
                or current["body"] is None
                or current["state"] not in {"RECEIVED", "PAUSED"}
            ):
                return
            self._prepare(current, version)

    def _prepare(self, row, version):
        document = decode(bytes(row["body"]))
        document["expectedVersion"] = version
        if row["kind"] == "CANCEL":
            target = self.get(row["target"])
            if not target or not target["operation_id"]:
                self.update(row["seq"], state="NOTICE", notice="NO_ACTIVE", body=None)
                return
            document["operationId"] = target["operation_id"]
        self.update(row["seq"], command=encode(document), body=None, state="PREPARED", attempts=0)

    def expire(self):
        """Não expirar comandos enviados sem resposta nem operações em andamento."""
        with self.db:
            self.db.execute(
                "DELETE FROM address_buttons WHERE scope=? AND expires<=?",
                (self.scope, self.clock()),
            )
            self.db.execute(
                "UPDATE conversation_outbox SET voice=NULL WHERE scope=? AND (created<=? OR state IN ('DONE','CANCELLED','EXPIRED','NOTICE'))",
                (self.scope, self.clock() - DAY),
            )
            self.db.execute(
                "UPDATE conversation_outbox SET body=NULL,command=NULL,state='NOTICE',notice='EXPIRED',attempts=0 "
                "WHERE scope=? AND (state IN ('RECEIVED','PREPARED') OR (state='PAUSED' AND body IS NOT NULL)) AND created<=?",
                (self.scope, self.clock() - DAY),
            )
            self.db.execute(
                "UPDATE conversation_outbox SET state='NOTICE',notice='CONTEXT_EXPIRED',attempts=0 "
                "WHERE scope=? AND kind='CONTEXT' AND state IN ('CONTEXT','PAUSED','DELIVERY_UNKNOWN') AND created<=?",
                (self.scope, self.clock() - DAY),
            )
            self.db.execute(
                "DELETE FROM conversation_outbox WHERE scope=? AND state IN ('DONE','CANCELLED','EXPIRED') "
                "AND created<?",
                (self.scope, self.clock() - 7 * DAY),
            )

    def status(self):
        rows = self.db.execute(
            "SELECT state,count(*) AS n FROM conversation_outbox WHERE scope=? "
            "AND state NOT IN ('DONE','CANCELLED','EXPIRED') GROUP BY state",
            (self.scope,),
        ).fetchall()
        if not rows:
            last = self.db.execute(
                "SELECT state,notice FROM conversation_outbox WHERE scope=? AND kind='TEXT' ORDER BY seq DESC LIMIT 1",
                (self.scope,),
            ).fetchone()
            if last:
                outcome = {
                    "SUCCEEDED": "concluído",
                    "FAILED": "falhou",
                    "CANCELLED": "interrompido",
                    "RESULT_UNKNOWN": "com resultado externo desconhecido",
                }.get(last["notice"] or last["state"])
                if outcome:
                    return "Último processamento: " + outcome + ". Não há mensagens pendentes."
            return "Não há mensagens pendentes."
        states = {
            "RECEIVED": "na fila",
            "PREPARED": "aguardando aceite",
            "POST_UNKNOWN": "aguardando confirmação de recebimento",
            "ACCEPTED": "em processamento ou entrega",
            "PAUSED": "acompanhamento pausado",
            "DELIVERY_UNKNOWN": "sem confirmação de entrega da resposta",
            "NOTICE": "aviso pendente",
        }
        return (
            "Em acompanhamento:\n"
            + "\n".join(f"• {r['n']} {states.get(r['state'], 'em acompanhamento')}" for r in rows)
            + "\n\nAs respostas chegam automaticamente enquanto o acompanhamento estiver ativo."
        )

    def delivered(self, seq, part):
        row = self.db.execute(
            "SELECT message_id FROM conversation_delivery WHERE seq=? AND part=?", (seq, part)
        ).fetchone()
        return row[0] if row else None

    def delivery_digest(self, seq, part):
        row = self.db.execute(
            "SELECT digest FROM conversation_delivery WHERE seq=? AND part=?", (seq, part)
        ).fetchone()
        return row[0] if row else None

    def record_delivery(self, seq, part, message_id, digest):
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO conversation_delivery VALUES (?,?,?,?)",
                (seq, part, message_id, digest),
            )

    def finish(self, seq):
        with self.db:
            self.update(seq, state="DONE", body=None, command=None, voice=None, attempts=0)
            self.db.execute("DELETE FROM conversation_delivery WHERE seq=?", (seq,))

    def pause_notice(self, row, code):
        """Aviso fixo independente: não apaga nem substitui o evento em recuperação."""
        event_id = row["event_id"] + "-paused"
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO conversation_outbox "
                "(scope,event_id,digest,kind,state,created,due,notice) VALUES (?,?,?,'INFO','NOTICE',?,?,?)",
                (self.scope, event_id, "technical-notice", self.clock(), self.clock(), code),
            )
