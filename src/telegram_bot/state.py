"""Cursor persistente e exclusão de processo; não armazena mensagens nem tokens."""

import os
import sqlite3
import time
from contextlib import contextmanager

WEEK = 7 * 24 * 60 * 60


@contextmanager
def single_instance(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("Outro processo usa este bot e diretório de estado.") from None
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


class State:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS cursor "
            "(id INTEGER PRIMARY KEY CHECK(id=1), offset INTEGER, updated REAL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS actions "
            "(update_id INTEGER PRIMARY KEY, created REAL NOT NULL)"
        )
        # Pergunta individual/grupo: só o último teclado enviado vale, e uma única vez.
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS mode_prompt "
            "(id INTEGER PRIMARY KEY CHECK(id=1), message_id INTEGER NOT NULL, used INTEGER NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS login_watch "
            "(id INTEGER PRIMARY KEY CHECK(id=1), owner INTEGER NOT NULL, "
            "attempt_id TEXT NOT NULL, started REAL NOT NULL, expires REAL NOT NULL, "
            "message_id INTEGER, phase TEXT NOT NULL, next_check REAL NOT NULL)"
        )
        self.db.commit()

    def close(self):
        self.db.close()

    def offset(self):
        row = self.db.execute("SELECT offset, updated FROM cursor WHERE id=1").fetchone()
        # Telegram pode escolher update_id aleatório após uma semana sem novos eventos.
        if not row or self.clock() - row[1] >= WEEK:
            return None
        return row[0]

    def done(self, update_id):
        with self.db:
            self.db.execute(
                "INSERT INTO cursor VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET offset=excluded.offset, updated=excluded.updated",
                (update_id + 1, self.clock()),
            )

    def claim_action(self, update_id):
        """Registrar ANTES de mutação HTTP; resultado desconhecido nunca dispara retry cego."""
        with self.db:
            self.db.execute("DELETE FROM actions WHERE created < ?", (self.clock() - WEEK,))
            result = self.db.execute(
                "INSERT OR IGNORE INTO actions VALUES (?, ?)", (update_id, self.clock())
            )
        return result.rowcount == 1

    def mode_prompt(self, message_id):
        with self.db:
            self.db.execute(
                "INSERT INTO mode_prompt VALUES (1, ?, 0) "
                "ON CONFLICT(id) DO UPDATE SET message_id=excluded.message_id, used=0",
                (message_id,),
            )

    def claim_mode(self, message_id):
        """Consome o teclado atual uma vez; antigo, repetido ou desconhecido não envia nada."""
        with self.db:
            result = self.db.execute(
                "UPDATE mode_prompt SET used=1 WHERE id=1 AND message_id=? AND used=0",
                (message_id,),
            )
        return result.rowcount == 1

    def login_watch(self):
        row = self.db.execute("SELECT * FROM login_watch WHERE id=1").fetchone()
        if row is None:
            return None
        return dict(
            zip(
                (
                    "id",
                    "owner",
                    "attempt_id",
                    "started",
                    "expires",
                    "message_id",
                    "phase",
                    "next_check",
                ),
                row,
            )
        )

    def watch_login(self, owner, attempt_id, expires):
        now = self.clock()
        current = self.login_watch()
        if current and current["owner"] == owner and current["attempt_id"] == attempt_id:
            with self.db:
                self.db.execute(
                    "UPDATE login_watch SET expires=? WHERE id=1",
                    (min(expires, current["started"] + 1200),),
                )
            return
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO login_watch VALUES (1, ?, ?, ?, ?, NULL, '', ?)",
                (owner, attempt_id, now, min(expires, now + 1200), now),
            )

    def login_message(self, attempt_id, message_id, phase):
        with self.db:
            self.db.execute(
                "UPDATE login_watch SET message_id=?, phase=? WHERE attempt_id=?",
                (message_id, phase, attempt_id),
            )

    def login_phase(self, phase, expires):
        with self.db:
            self.db.execute(
                "UPDATE login_watch SET phase=?, expires=? WHERE id=1", (phase, expires)
            )

    def login_next_check(self, when):
        with self.db:
            self.db.execute("UPDATE login_watch SET next_check=? WHERE id=1", (when,))

    def stop_login_watch(self):
        with self.db:
            self.db.execute("DELETE FROM login_watch")
