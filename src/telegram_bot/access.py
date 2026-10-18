"""Entrada privada por senha da demo. Nunca persiste senha, mensagem ou identidade iFood."""

import hashlib
import hmac
import sqlite3
import time
from contextlib import closing, contextmanager

SESSION_SECONDS = 86400
WINDOW = 900


class AccessStore:
    def __init__(self, path, password, token, *, clock=time.time, capacity=100):
        self.path, self.clock, self.capacity = path, clock, capacity
        self.expected = hashlib.sha256(password.encode()).digest()
        self.epoch = hmac.new(token.encode(), password.encode(), hashlib.sha256).hexdigest()
        path.touch(mode=0o600, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS access_grants "
            "(owner INTEGER PRIMARY KEY, epoch TEXT NOT NULL, expires REAL NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS access_attempts "
            "(owner INTEGER PRIMARY KEY, started REAL NOT NULL, attempts INTEGER NOT NULL, "
            "notice REAL NOT NULL DEFAULT 0)"
        )
        self.db.commit()

        self.db.execute(
            "CREATE TABLE IF NOT EXISTS access_entry (owner INTEGER PRIMARY KEY, expires REAL NOT NULL)"
        )
        self.db.commit()

    def request_entry(self, owner):
        with self.db:
            self.db.execute("DELETE FROM access_entry WHERE expires<=?", (self.clock(),))
            if self.db.execute("SELECT count(*) FROM access_entry").fetchone()[0] >= 1000:
                return False
            self.db.execute(
                "INSERT OR REPLACE INTO access_entry VALUES (?,?)", (owner, self.clock() + 300)
            )
        return True

    def awaiting_entry(self, owner):
        return (
            self.db.execute(
                "SELECT 1 FROM access_entry WHERE owner=? AND expires>?", (owner, self.clock())
            ).fetchone()
            is not None
        )

    def expired_entry(self, owner):
        return (
            self.db.execute(
                "SELECT 1 FROM access_entry WHERE owner=? AND expires<=?", (owner, self.clock())
            ).fetchone()
            is not None
        )

    def clear_entry(self, owner):
        with self.db:
            self.db.execute("DELETE FROM access_entry WHERE owner=?", (owner,))

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def allowed(self, owner):
        return (
            self.db.execute(
                "SELECT 1 FROM access_grants WHERE owner=? AND epoch=? AND expires>?",
                (owner, self.epoch, self.clock()),
            ).fetchone()
            is not None
        )

    def owners(self):
        with self.db:
            self.db.execute(
                "DELETE FROM access_grants WHERE expires<=? OR epoch<>?", (self.clock(), self.epoch)
            )
            self.db.execute(
                "DELETE FROM access_attempts WHERE started<=?", (self.clock() - WINDOW,)
            )
        return [
            r[0]
            for r in self.db.execute(
                "SELECT owner FROM access_grants WHERE epoch=? AND expires>? ORDER BY owner",
                (self.epoch, self.clock()),
            )
        ]

    def revoke(self, owner):
        with self.db:
            self.db.execute("DELETE FROM access_grants WHERE owner=?", (owner,))

    def notice(self, owner):
        now = self.clock()
        with self.db:
            self.db.execute("DELETE FROM access_attempts WHERE started<=?", (now - WINDOW,))
            row = self.db.execute(
                "SELECT notice FROM access_attempts WHERE owner=?", (owner,)
            ).fetchone()
            if row and now - row[0] < 60:
                return False
            if (
                not row
                and self.db.execute("SELECT count(*) FROM access_attempts").fetchone()[0] >= 1000
            ):
                return False
            self.db.execute(
                "INSERT INTO access_attempts VALUES (?,?,0,?) ON CONFLICT(owner) "
                "DO UPDATE SET notice=excluded.notice",
                (owner, now, now),
            )
        return True

    def enter(self, owner, candidate):
        now = self.clock()
        # Reserva tentativa antes da comparação. Inclusive senha correta respeita bloqueio temporário.
        with self.transaction():
            self.db.execute("DELETE FROM access_attempts WHERE started<=?", (now - WINDOW,))
            self.db.execute(
                "DELETE FROM access_grants WHERE expires<=? OR epoch<>?", (now, self.epoch)
            )
            row = self.db.execute(
                "SELECT attempts FROM access_attempts WHERE owner=?", (owner,)
            ).fetchone()
            total = self.db.execute(
                "SELECT coalesce(sum(attempts),0) FROM access_attempts"
            ).fetchone()[0]
            if (row and row[0] >= 5) or total >= 100:
                return "LIMIT"
            self.db.execute(
                "INSERT INTO access_attempts(owner,started,attempts) VALUES (?,?,1) "
                "ON CONFLICT(owner) DO UPDATE SET attempts=attempts+1",
                (owner, now),
            )
            if len(candidate) > 80 or not hmac.compare_digest(
                hashlib.sha256(candidate.encode()).digest(), self.expected
            ):
                return "DENIED"
            count = self.db.execute("SELECT count(*) FROM access_grants").fetchone()[0]
            if count >= self.capacity and not self.allowed(owner):
                return "FULL"
            self.db.execute(
                "INSERT INTO access_grants VALUES (?,?,?) ON CONFLICT(owner) DO UPDATE SET "
                "epoch=excluded.epoch, expires=excluded.expires",
                (owner, self.epoch, now + SESSION_SECONDS),
            )
            return "OK"

    def checker(self, owner):
        # Conexão curta própria da thread do worker; nunca compartilhar sqlite.Connection entre threads.
        def check():
            with closing(sqlite3.connect(self.path, timeout=10)) as db:
                return (
                    db.execute(
                        "SELECT 1 FROM access_grants WHERE owner=? AND epoch=? AND expires>?",
                        (owner, self.epoch, self.clock()),
                    ).fetchone()
                    is not None
                )

        return check
