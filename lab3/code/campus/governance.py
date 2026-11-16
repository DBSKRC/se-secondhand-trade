"""Reports, moderator actions, and append-only dispute opinions."""

from campus import auth
from campus import catalog
from campus import commands
from campus import domain
from campus import storage
from campus import trades


class Governance(commands.Service):
    """Apply administrator decisions and preserve their history."""

    def submit_report(self, token, item_id, reason, key):
        """Record a member complaint and return its tracking number."""
        with self.command(
            token, "member", "report", "item", item_id,
        ) as (cx, actor):
            reason = domain.required("举报原因", reason, 1000)

            def insert():
                storage.fetch(cx, "items", item_id, "商品")
                cursor = cx.execute(
                    """
                    INSERT INTO reports(item_id, reporter_id, reason,
                                        created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (item_id, actor, reason, self.database.now()),
                )
                self.database.audit(
                    cx, actor, "submit", "report", cursor.lastrowid,
                    after="open",
                )
                return cursor.lastrowid

            return storage.once(
                cx, actor, "report", key, [item_id, reason],
                insert,
            )

    def resolve_report(self, token, report_id, result, decision=None,
                       reason=""):
        """Record a result and any product action in the same transaction."""
        with self.command(
            token, "admin", "resolve", "report", report_id,
        ) as (cx, actor):
            report = storage.fetch(cx, "reports", report_id, "举报")
            if report["handled_at"] is not None:
                raise domain.RuleError("举报已处理，请刷新")
            result = domain.required("处理结果", result, 1000)
            if decision:
                self._moderate(cx, actor, report["item_id"], decision, reason)
            cx.execute(
                """
                UPDATE reports SET admin_id = ?, result = ?, handled_at = ?
                WHERE id = ?
                """,
                (actor, result, self.database.now(), report_id),
            )
            self.database.audit(
                cx, actor, "resolve", "report", report_id, "open", "handled",
            )

    def moderate(self, token, item_id, decision, reason):
        """Withdraw or freeze a product with a recorded reason."""
        with self.command(
            token, "admin", decision, "item", item_id,
        ) as (cx, actor):
            return self._moderate(cx, actor, item_id, decision, reason)

    def _moderate(self, connection, actor, item_id, decision, reason):
        item = storage.fetch(connection, "items", item_id, "商品")
        before = item["state"]
        reason = domain.required("处理原因", reason, 1000)
        now = self.database.now()
        if decision == "withdraw" and before == "published":
            after = "withdrawn"
        elif decision == "freeze" and before in {
            "published", "reserved", "trading",
        }:
            after = "frozen"
            self._freeze_reservation(connection, actor, item_id, reason, now)
        else:
            raise domain.RuleError("当前状态不允许该处置，请刷新")
        catalog.change_state(connection, item_id, after, now)
        self.database.audit(
            connection, actor, decision, "item", item_id, before, after, reason,
        )
        return after

    def _freeze_reservation(self, connection, actor, item_id, reason, now):
        reservation = trades.active_reservation(connection, item_id)
        if reservation is None:
            return
        before = reservation["state"]
        if before == "disputed":
            return
        after = "cancelled" if before == "pending" else "disputed"
        reservation_id = reservation["id"]
        trades.update_reservation(
            connection, reservation_id, after, reason, now,
        )
        if after == "disputed":
            connection.execute(
                """
                INSERT INTO disputes(reservation_id, reason,
                                     created_at)
                VALUES (?, ?, ?)
                """,
                (reservation_id, reason, now),
            )
        self.database.audit(
            connection, actor, "freeze", "reservation", reservation_id,
            before, after, reason,
        )

    def add_opinion(self, token, dispute_id, opinion):
        """Append an opinion while keeping the existing dispute state."""
        with self.command(
            token, "admin", "opinion", "dispute", dispute_id,
        ) as (cx, actor):
            storage.fetch(cx, "disputes", dispute_id, "争议")
            opinion = domain.required("处理意见", opinion, 2000)
            cursor = cx.execute(
                """
                INSERT INTO dispute_notes(dispute_id, admin_id, body,
                                          created_at)
                VALUES (?, ?, ?, ?)
                """,
                (dispute_id, actor, opinion, self.database.now()),
            )
            self.database.audit(cx, actor, "opinion", "dispute", dispute_id)
            return cursor.lastrowid

    def reports(self, token, open_only=False):
        """List reports for an administrator."""
        with self.database.snapshot() as cx:
            auth.identify(cx, token, self.database.now(), "admin")
            rows = cx.execute(
                """
                SELECT p.*, i.title FROM reports AS p
                JOIN items AS i ON i.id = p.item_id
                WHERE ? = 0 OR p.handled_at IS NULL
                ORDER BY p.id DESC
                """,
                (int(open_only),),
            )
            return [dict(row) for row in rows]

    def disputes(self, token, dispute_id=None):
        """Read disputes and opinions from a consistent snapshot."""
        with self.database.snapshot() as cx:
            auth.identify(cx, token, self.database.now(), "admin")
            rows = cx.execute(
                """
                SELECT d.*, r.item_id, r.buyer_id, r.state,
                       r.price_cents, i.title, i.seller_id
                FROM disputes AS d
                JOIN reservations AS r ON r.id = d.reservation_id
                JOIN items AS i ON i.id = r.item_id
                WHERE ? IS NULL OR d.id = ?
                ORDER BY d.id DESC
                """,
                (dispute_id, dispute_id),
            )
            result = [dict(row) for row in rows]
            if dispute_id is not None and not result:
                raise domain.RuleError("争议不存在")
            for record in result:
                notes = cx.execute(
                    """
                    SELECT id, admin_id, body, created_at FROM dispute_notes
                    WHERE dispute_id = ? ORDER BY id
                    """,
                    (record["id"],),
                )
                record["opinions"] = [dict(row) for row in notes]
            return result
