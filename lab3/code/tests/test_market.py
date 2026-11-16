"""Verify persistence, authorization, and transaction boundaries."""

import concurrent.futures
import pathlib
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

from campus import catalog
from campus import domain
from campus import interface
from campus import storage


# The fixture keeps separate sessions and services for authorization tests.
# pylint: disable-next=too-many-instance-attributes
class MarketTest(unittest.TestCase):
    """Exercise real services and temporary SQLite files."""

    def setUp(self):
        # unittest closes registered contexts even when setup fails.
        # pylint: disable-next=consider-using-with
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.root = pathlib.Path(directory)
        self.now = 1_800_000_000
        self.db = storage.Database(self.root / "market.db", lambda: self.now)
        self.db.initialize()
        self.app = interface.Application(self.db, 5)
        accounts = self.app.accounts
        accounts.bootstrap_admin("admin", "admin-pass")
        for name in ("seller", "buyer", "other"):
            accounts.register(name, "test-pass")
        self.admin = accounts.login("admin", "admin-pass")
        self.seller = accounts.login("seller", "test-pass")
        self.buyer = accounts.login("buyer", "test-pass")
        self.other = accounts.login("other", "test-pass")
        self.catalog = self.app.catalog
        self.trades = self.app.trades
        self.moderation = self.app.governance

    def form(self, price="10.25"):
        """Create a valid form with a selectable price."""
        return catalog.item_payload("算法教材", "使用一学期", "books", "good", price)

    def publish(self, key="first"):
        """Save and approve one product."""
        item_id = self.catalog.create(self.seller, key, self.form())
        self.catalog.seller_action(self.seller, item_id, "submit")
        self.catalog.review(self.admin, item_id, True, "描述齐全")
        return item_id

    def reserve(self, item, key="first"):
        """Reserve the current published version."""
        view = self.catalog.detail(None, item)
        return self.trades.reserve(
            self.buyer, item, view["price_cents"], view["version"], key,
        )["id"]

    def get_booking(self, booking):
        """Read one buyer-visible booking."""
        return self.trades.records(self.buyer, "buy", booking)[0]

    def test_review_and_login_boundaries(self):
        """Reject invalid prices, invisible drafts and role violations."""
        with self.assertRaisesRegex(domain.RuleError, "价格"):
            self.form("-1")
        with self.assertRaisesRegex(domain.RuleError, "账号已存在"):
            self.app.accounts.register("SELLER", "test-pass")
        with self.assertRaisesRegex(domain.RuleError, "账号或密码"):
            self.app.accounts.login("seller", "wrong")
        payload = self.form()
        draft = self.catalog.create(self.seller, "create", payload)
        self.assertEqual(
            draft,
            self.catalog.create(self.seller, "create", payload),
        )
        with self.assertRaisesRegex(domain.RuleError, "不同内容"):
            self.catalog.create(self.seller, "create", self.form("8"))
        self.assertEqual(0, self.catalog.search()["total"])
        with self.assertRaisesRegex(domain.RuleError, "不可公开"):
            self.catalog.detail(None, draft)
        with self.assertRaisesRegex(domain.RuleError, "请先登录"):
            self.catalog.seller_action(None, draft, "submit")
        with self.assertRaisesRegex(domain.RuleError, "自己的"):
            self.catalog.revise(self.buyer, draft, payload)
        self.catalog.seller_action(self.seller, draft, "submit")
        with self.assertRaisesRegex(domain.RuleError, "无权"):
            self.catalog.review(self.buyer, draft, True, "违规提权测试")
        self.catalog.review(self.admin, draft, False, "补描述")
        self.assertEqual(
            "补描述",
            self.catalog.detail(self.seller, draft)["reviews"][0]["reason"],
        )
        self.catalog.revise(self.seller, draft, payload)
        self.catalog.seller_action(self.seller, draft, "submit")
        self.catalog.review(self.admin, draft, True, "通过")
        filtered = self.catalog.search(
            keyword="教材", category="books", minimum=1000, maximum=1100,
        )
        self.assertEqual([draft], [row["id"] for row in filtered["items"]])

    def test_complete_and_scope(self):
        """Require both parties and persist the completed trade."""
        product = self.publish()
        booking = self.reserve(product)
        with self.assertRaisesRegex(domain.RuleError, "没有权限"):
            self.trades.act(self.other, booking, "accept")
        with self.assertRaisesRegex(domain.RuleError, "预约状态"):
            self.trades.act(self.buyer, booking, "complete")
        self.trades.act(self.seller, booking, "accept")
        with self.assertRaisesRegex(domain.RuleError, "预约状态"):
            self.trades.act(self.buyer, booking, "cancel")
        self.trades.act(self.seller, booking, "deliver")
        self.assertEqual("trading", self.get_booking(booking)["item_state"])
        self.trades.act(self.buyer, booking, "complete")
        result = self.get_booking(booking)
        self.assertEqual(("completed", "completed", 1025),
                         (result["state"], result["item_state"],
                          result["price_cents"]))
        stats = self.app.analytics.summary(self.seller, "mine")
        self.assertEqual(1, stats["completed"])
        self.assertEqual(1, stats["item_states"]["completed"])
        self.assertEqual(
            0,
            self.app.analytics.summary(self.other, "mine")["items"],
        )
        with self.assertRaises(domain.RuleError):
            self.app.analytics.audit_log(self.buyer)
        logs = self.app.analytics.audit_log(self.admin, outcome="denied")
        self.assertTrue(any(row["action"] == "accept" for row in logs))
        with self.db.connection() as connection:
            self.assertEqual(1, connection.execute(
                "SELECT COUNT(*) FROM reservations WHERE state = 'completed'",
            ).fetchone()[0])

    def test_expiry_and_version(self):
        """Close overdue requests and refuse stale prices and versions."""
        product = self.publish()
        old = self.catalog.detail(None, product)
        booking = self.reserve(product)
        self.now += 5
        with self.assertRaisesRegex(domain.RuleError, "已超时"):
            self.trades.act(self.seller, booking, "accept")
        self.assertEqual(1, self.trades.expire())
        self.assertEqual("超时", self.get_booking(booking)["closed_reason"])
        self.catalog.revise(self.seller, product, self.form("12"))
        self.catalog.review(self.admin, product, True, "新的价格")
        with self.assertRaisesRegex(domain.RuleError, "价格或版本"):
            self.trades.reserve(
                self.buyer, product, 1025, old["version"], "old",
            )
        new_booking = self.reserve(product, "second")
        self.assertEqual(1025, self.get_booking(booking)["price_cents"])
        self.assertEqual(1200, self.get_booking(new_booking)["price_cents"])
        with self.assertRaisesRegex(domain.RuleError, "原因"):
            self.trades.act(self.seller, new_booking, "reject")
        self.trades.act(self.seller, new_booking, "reject", "已无空闲")
        self.assertEqual(
            "published",
            self.get_booking(new_booking)["item_state"],
        )

    def test_moderation_and_disputes(self):
        """Retain histories and roll back invalid report resolution."""
        item = self.publish()
        booking = self.reserve(item)
        report = self.moderation.submit_report(self.other, item, "举报内容", "r")
        with self.assertRaises(domain.RuleError):
            self.moderation.resolve_report(
                self.admin, report, "结果", "withdraw", "x",
            )
        self.assertIsNone(self.moderation.reports(self.admin)[0]["result"])
        self.moderation.resolve_report(self.admin, report, "成立", "freeze", "原因")
        result = self.get_booking(booking)
        self.assertEqual(
            ("cancelled", "frozen"),
            (result["state"], result["item_state"]),
        )
        other = self.publish("trade")
        trading = self.reserve(other, "trade")
        self.trades.act(self.seller, trading, "accept")
        self.trades.act(self.seller, trading, "deliver")
        self.trades.act(self.buyer, trading, "dispute", "记载争议")
        self.moderation.moderate(self.admin, other, "freeze", "保留交易")
        dispute = self.moderation.disputes(self.admin)[0]
        self.moderation.add_opinion(self.admin, dispute["id"], "第一次意见")
        self.moderation.add_opinion(self.admin, dispute["id"], "补充意见")
        result = self.moderation.disputes(self.admin, dispute["id"])[0]
        self.assertEqual(2, len(result["opinions"]))
        self.assertEqual("disputed", result["state"])
        self.assertTrue(self.app.maintenance.inspect(self.admin)["healthy"])

    def test_creation_rollback(self):
        """Simulate a write failure after changing the reservation."""
        product = self.publish()
        with self.db.write() as cx:
            cx.execute("""
                CREATE TRIGGER fail_reserve BEFORE UPDATE ON items
                WHEN NEW.state = 'reserved'
                BEGIN SELECT RAISE(ABORT, 'simulated failure'); END
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.reserve(product)
        self.assertEqual([], self.trades.records(self.buyer))
        self.assertEqual(
            "published",
            self.catalog.detail(None, product)["state"],
        )

    def test_concurrent_reservations(self):
        """Only one buyer can win and a repeat request replays its result."""
        product = self.publish()
        view = self.catalog.detail(None, product)
        barrier = threading.Barrier(2)

        def attempt(token):
            barrier.wait(timeout=5)
            try:
                response = self.trades.reserve(
                    token, product, 1025, view["version"], "duplicate",
                )
                return token, response
            except domain.RuleError:
                return token, None

        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            outcomes = list(pool.map(attempt, [self.buyer, self.other]))
        [(winner, record)] = [row for row in outcomes if row[1]]
        self.assertEqual(record, self.trades.reserve(
            winner, product, 1025, view["version"], "duplicate",
        ))
        self.assertEqual(
            "reserved",
            self.catalog.detail(self.seller, product)["state"],
        )
        self.assertEqual(1, len(self.trades.records(self.seller, "sell")))

    def test_command_dispatch_and_backup(self):
        """Use the normal parser and verify a backup excludes sessions."""
        with mock.patch("getpass.getpass", return_value="test-pass"):
            self.app.execute(["login", "seller"])
        item = self.app.execute(["create", "台灯", "完好", "10"])["item_id"]
        self.app.execute(["submit", str(item)])
        self.app.token = self.admin
        self.app.execute(["review", str(item), "approve", "检查完毕"])
        self.assertEqual(1, self.app.execute(["search", "--min", "5"])["total"])
        target = self.root / "backup.db"
        self.app.execute(["backup", str(target)])
        with storage.Database(target).connection() as cx:
            self.assertEqual(
                0,
                cx.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
            )
            self.assertEqual(
                1,
                cx.execute("SELECT COUNT(*) FROM items").fetchone()[0],
            )

    def test_cancel_accept_race(self):
        """A stale action cannot overwrite a concurrently accepted command."""
        item = self.publish()
        booking = self.reserve(item)
        gate = threading.Barrier(2)

        def attempt(command):
            token, action = command
            gate.wait(timeout=5)
            try:
                return self.trades.act(token, booking, action)
            except domain.RuleError:
                return None

        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(
                attempt, [(self.buyer, "cancel"), (self.seller, "accept")],
            ))
        record = self.get_booking(booking)
        [winner] = [state for state in results if state is not None]
        self.assertEqual(winner, record["state"])
        expected = "published" if winner == "cancelled" else "trading"
        self.assertEqual(expected, record["item_state"])


if __name__ == "__main__":
    unittest.main()
