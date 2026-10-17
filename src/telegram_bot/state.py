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
