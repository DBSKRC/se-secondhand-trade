"""Database consistency diagnostics and verified snapshots."""

import contextlib
import pathlib
import sqlite3

from campus import auth
from campus import commands
from campus import domain

_EXPECTED_ITEM_STATES = {
    "pending": ("reserved",),
    "trading": ("trading",),
    "delivered": ("trading",),
    "disputed": ("trading", "frozen"),
}


class Maintenance(commands.Service):
    """Inspect business invariants and export consistent backups."""

    def inspect(self, token):
        """List current data issues for an authenticated administrator."""
        with self.database.snapshot() as cx:
            auth.identify(cx, token, self.database.now(), "admin")
            corruption = [
                row[0] for row in cx.execute("PRAGMA quick_check")
                if row[0] != "ok"
            ]
            foreign_keys = [
                dict(row) for row in cx.execute("PRAGMA foreign_key_check")
            ]
            reservations = self._reservation_issues(cx)
            disputes = self._dispute_issues(cx)
            return {
                "healthy": not any(
                    (corruption, foreign_keys, reservations, disputes),
                ),
                "integrity": [{"detail": entry} for entry in corruption],
                "foreign_keys": foreign_keys,
                "reservation_issues": reservations,
                "dispute_issues": disputes,
            }

    @staticmethod
    def _reservation_issues(connection):
        rows = connection.execute(
            """
            SELECT i.id, i.state, r.id AS reservation_id,
                   r.state AS reservation_state
            FROM items AS i LEFT JOIN reservations AS r
              ON r.item_id = i.id
             AND r.state IN ('pending', 'trading', 'delivered', 'disputed')
            WHERE r.id IS NOT NULL OR i.state IN ('reserved', 'trading')
            ORDER BY i.id
            """,
        )
        issues = []
        for row in rows:
            state = row["reservation_state"]
            if state is None:
                reason = "占用状态的商品缺少有效预约"
            elif row["state"] not in _EXPECTED_ITEM_STATES[state]:
                reason = "有效预约与商品状态不匹配"
            else:
                continue
            issues.append({
                "item_id": row["id"],
                "state": row["state"],
                "reservation_id": row["reservation_id"],
                "reservation_state": state,
                "reason": reason,
            })
        return issues

    @staticmethod
    def _dispute_issues(connection):
        rows = connection.execute(
            """
            SELECT r.id AS reservation_id, d.id AS dispute_id
            FROM reservations AS r LEFT JOIN disputes AS d
              ON d.reservation_id = r.id
            WHERE (r.state = 'disputed' AND d.id IS NULL)
               OR (r.state <> 'disputed' AND d.id IS NOT NULL)
            ORDER BY r.id
            """,
        )
        return [
            dict(row, reason="争议记录与预约状态不匹配") for row in rows
        ]

    def backup(self, token, destination):
        """Save a consistent copy at a new path and verify its integrity."""
        destination = pathlib.Path(destination)
        if not destination.parent.is_dir():
            raise domain.RuleError("备份目录不存在")
        with self.database.connection() as source:
            auth.identify(source, token, self.database.now(), "admin")
            with destination.open("xb"):
                pass
            try:
                self._copy(source, destination)
            except (OSError, sqlite3.Error, domain.RuleError):
                destination.unlink(missing_ok=True)
                raise
        return str(destination)

    @staticmethod
    def _copy(source, destination):
        with contextlib.closing(sqlite3.connect(destination)) as target:
            source.backup(target, pages=128)
            # Session tokens are only valid in the original database.
            with target:
                target.execute("DELETE FROM sessions")
            integrity = target.execute("PRAGMA quick_check").fetchall()
            if integrity != [("ok",)]:
                raise domain.RuleError("备份一致性检查失败")
