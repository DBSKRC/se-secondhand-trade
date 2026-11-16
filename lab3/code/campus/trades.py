"""Reservation state transitions, expiry, and buyer/seller queries."""

import contextlib
import logging
import sqlite3
import threading

from campus import auth
from campus import catalog
from campus import commands
from campus import domain
from campus import storage


class Trades(commands.Service):
    """Coordinate reservation and product updates in one transaction."""

    def __init__(self, database, deadline_seconds=86400):
        super().__init__(database)
        if deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")
        self.deadline_seconds = deadline_seconds

    def reserve(self, token, item_id, seen_price, seen_version, request_key):
        """Reserve at the price and version explicitly seen by the buyer."""
        payload = [item_id, seen_price, seen_version]
        with self.command(
            token, "member", "reserve", "item", item_id,
        ) as (cx, actor):
            return storage.once(
                cx, actor, "reserve", request_key, payload,
                lambda: self._reserve(cx, actor, *payload),
            )

    def _reserve(self, connection, actor, item_id, price, version):
        item = storage.fetch(connection, "items", item_id, "商品")
        if item["seller_id"] == actor:
            raise domain.RuleError("不能预约自己发布的商品")
        active = active_reservation(connection, item_id)
        if active is not None:
            if active["buyer_id"] == actor:
                raise domain.RuleError("已有有效预约，请查看买入记录")
            raise domain.RuleError("商品已被预约，请刷新")
        if item["price_cents"] != price or item["version"] != version:
            raise domain.RuleError("商品价格或版本已变化，请刷新后确认")
        if item["state"] != "published":
            raise domain.RuleError("商品当前不可预约，请刷新")
        now = self.database.now()
        cursor = connection.execute(
            """
            INSERT INTO reservations(item_id, buyer_id, price_cents, state,
                                     created_at, updated_at, expires_at)
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """,
            (item_id, actor, price, now, now, now + self.deadline_seconds),
        )
        reservation_id = cursor.lastrowid
        catalog.change_state(connection, item_id, "reserved", now)
        self.database.audit(
            connection, actor, "reserve", "reservation", reservation_id,
            after="pending",
        )
        self.database.audit(
            connection, actor, "reserve", "item", item_id,
            "published", "reserved",
        )
        return {"id": reservation_id, "price_cents": price, "state": "pending"}

    def act(self, token, reservation_id, action, reason=""):
        """Apply a state change only for the correct transaction party."""
        if action not in domain.TRANSITIONS:
            raise domain.RuleError("未知预约操作")
        expected, party, after, item_after = domain.TRANSITIONS[action]
        with self.command(
            token, "member", action, "reservation", reservation_id,
        ) as (cx, actor):
            record = storage.fetch(cx, "reservations", reservation_id, "预约")
            item = storage.fetch(cx, "items", record["item_id"], "商品")
            allowed = (
                record["buyer_id"] if party == "buyer" else item["seller_id"]
            )
            if actor != allowed:
                raise domain.RuleError("没有权限操作该预约")
            now = self.database.now()
            if action == "accept" and (
                record["closed_reason"] == "超时"
                or (
                    record["state"] == "pending" and record["expires_at"] <= now
                )
            ):
                raise domain.RuleError("预约已超时，请刷新")
            if record["state"] != expected:
                raise domain.RuleError("当前预约状态不允许此操作，请刷新")
            if record["state"] == "pending" and record["expires_at"] <= now:
                raise domain.RuleError("预约已超时，请刷新")
            if action in {"reject", "dispute"}:
                reason = domain.required("原因", reason, 1000)
            update_reservation(cx, reservation_id, after, reason, now)
            catalog.change_state(cx, item["id"], item_after, now)
            if action == "dispute":
                cx.execute(
                    """
                    INSERT INTO disputes(reservation_id, reason,
                                         created_at)
                    VALUES (?, ?, ?)
                    """,
                    (reservation_id, reason, now),
                )
            self.database.audit(
                cx, actor, action, "reservation", reservation_id,
                expected, after, reason,
            )
            self.database.audit(
                cx, actor, action, "item", item["id"], item["state"],
                item_after,
            )
            return after

    def expire(self):
        """Close every due pending reservation, preserving all history."""
        with self.database.write() as cx:
            now = self.database.now()
            due = cx.execute(
                """
                SELECT id, item_id FROM reservations
                WHERE state = 'pending' AND expires_at <= ? ORDER BY id
                """,
                (now,),
            ).fetchall()
            for row in due:
                update_reservation(cx, row["id"], "cancelled", "超时", now)
                catalog.change_state(cx, row["item_id"], "published", now)
                self.database.audit(
                    cx, None, "expire", "reservation", row["id"],
                    "pending", "cancelled", "超时",
                )
                self.database.audit(
                    cx, None, "expire", "item", row["item_id"],
                    "reserved", "published",
                )
            return len(due)

    def records(self, token, side="buy", reservation_id=None):
        """Return records only for the caller's chosen participation role."""
        roles = {"buy": "r.buyer_id", "sell": "i.seller_id"}
        if side not in roles:
            raise domain.RuleError("记录类型须为 buy 或 sell")
        with self.database.snapshot() as cx:
            user = auth.identify(cx, token, self.database.now(), "member")
            restriction = " AND r.id = ?" if reservation_id is not None else ""
            args = (user["id"],)
            if reservation_id is not None:
                args += (reservation_id,)
            rows = cx.execute(
                f"""
                SELECT r.*, i.title, i.seller_id, i.state AS item_state
                FROM reservations AS r JOIN items AS i ON i.id = r.item_id
                WHERE {roles[side]} = ? {restriction}
                ORDER BY r.id DESC
                """,
                args,
            )
            result = [dict(row) for row in rows]
            if reservation_id is not None and not result:
                raise domain.RuleError("预约不存在或无权查看")
            return result

    @contextlib.contextmanager
    def expiry_worker(self, seconds=1.0):
        """Periodically close due bookings while the application runs."""
        stop = threading.Event()

        def run():
            while not stop.wait(seconds):
                try:
                    self.expire()
                except sqlite3.Error:
                    logging.exception("预约自动关闭失败，下轮重试")

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            yield
        finally:
            stop.set()
            worker.join()


def active_reservation(connection, item_id):
    """Return the active booking of an item, if any."""
    return connection.execute(
        """
        SELECT * FROM reservations WHERE item_id = ?
        AND state IN ('pending', 'trading', 'delivered', 'disputed')
        """,
        (item_id,),
    ).fetchone()


def update_reservation(connection, reservation_id, state, reason, now):
    """Change reservation state without touching its price snapshot."""
    connection.execute(
        """
        UPDATE reservations
        SET state = ?, closed_reason = ?, updated_at = ?, completed_at = ?
        WHERE id = ?
        """,
        (state, reason, now, now if state == "completed" else None,
         reservation_id),
    )
