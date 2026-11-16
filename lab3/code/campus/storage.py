"""SQLite connections, write transactions, audit, and idempotency."""

import contextlib
import hashlib
import json
import pathlib
import sqlite3
import time

from campus import domain


class Database:
    """Own the file path and open a connection per operation."""

    def __init__(self, path, clock=time.time):
        self.path = pathlib.Path(path)
        self.clock = clock

    def now(self) -> int:
        """Return UTC epoch seconds from the configured clock."""
        return int(self.clock())

    def initialize(self):
        """Create the database and schema when absent."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        schema = pathlib.Path(__file__).with_name("schema.sql")
        with self.connection() as connection:
            connection.executescript(schema.read_text(encoding="utf-8"))

    @contextlib.contextmanager
    def connection(self):
        """Yield a configured connection, then close it."""
        connection = sqlite3.connect(
            self.path, timeout=10, isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    @contextlib.contextmanager
    def write(self):
        """Lock before reading write preconditions and commit as a unit."""
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @contextlib.contextmanager
    def snapshot(self):
        """Keep a consistent read snapshot across multiple queries."""
        with self.connection() as connection:
            connection.execute("BEGIN")
            yield connection

    def audit(self, connection, actor, action, entity, entity_id=None,
              before=None, after=None, detail="", outcome="ok"):
        """Append an audit event in the caller's transaction."""
        connection.execute(
            """
            INSERT INTO audit(actor_id, action, entity, entity_id,
                              before_state, after_state, detail, outcome,
                              created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (actor, action, entity, entity_id, before, after, detail, outcome,
             self.now()),
        )

    def denied(self, actor, action, entity, entity_id, error):
        """Persist a rejected command after its transaction rolls back."""
        with self.write() as connection:
            self.audit(
                connection, actor, action, entity, entity_id,
                detail=str(error), outcome="denied",
            )


def fetch(connection, table, entity_id, label):
    """Fetch an entity from a fixed allowlist of tables."""
    if table not in {"items", "reservations", "reports", "disputes"}:
        raise ValueError("unsupported entity table")
    row = connection.execute(
        f"SELECT * FROM {table} WHERE id = ?", (entity_id,),
    ).fetchone()
    if row is None:
        raise domain.RuleError(f"{label}不存在")
    return row


def once(connection, actor, operation, key, payload, execute):
    """Replay a matching request or save its successful response."""
    key = domain.required("请求编号", key, 100)
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
    previous = connection.execute(
        """
        SELECT fingerprint, response FROM requests
        WHERE actor_id = ? AND operation = ? AND request_key = ?
        """,
        (actor, operation, key),
    ).fetchone()
    if previous is not None:
        if previous["fingerprint"] != fingerprint:
            raise domain.RuleError("同一请求编号不能用于不同内容")
        return json.loads(previous["response"])
    response = execute()
    connection.execute(
        "INSERT INTO requests VALUES (?, ?, ?, ?, ?)",
        (actor, operation, key, fingerprint, json.dumps(response)),
    )
    return response
