"""Verify the mobile API over real local HTTP requests."""

import http.cookiejar
import json
import pathlib
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from campus import mobile
from campus import mobile_api
from campus import domain
from campus import storage


class Client:
    """Model one browser with a cookie jar."""

    def __init__(self, url):
        self.url = url
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )

    def action(self, name, fields=None, origin=None):
        """Perform a same-origin request and decode JSON."""
        data = None if fields is None else json.dumps(fields).encode()
        request = urllib.request.Request(
            self.url + "/api/" + name,
            data,
            {"Content-Type": "application/json", "Origin": origin or self.url},
        )
        with self.opener.open(request, timeout=10) as response:
            return json.load(response)


class MobileTest(unittest.TestCase):
    """Run a fresh HTTP server against a temporary database."""

    def setUp(self):
        # unittest closes registered contexts even when setup fails.
        # pylint: disable-next=consider-using-with
        directory = self.enterContext(tempfile.TemporaryDirectory())
        database = storage.Database(pathlib.Path(directory) / "mobile.db")
        database.initialize()
        api = mobile_api.Api(database)
        with self.assertRaisesRegex(domain.RuleError, "未知操作"):
            api.call(None, "not-an-action", {})
        server = self.enterContext(mobile.LocalServer(("127.0.0.1", 0), api))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_port}"

    def test_transaction_with_separate_sessions(self):
        """Check the buyer, seller and admin maintain separate identities."""
        password = "test-password"
        moderator, seller, buyer = (Client(self.url) for _ in range(3))
        for client, account, action in (
            (moderator, "mod", "setup"),
            (seller, "seller", "register"),
            (buyer, "buyer", "register"),
        ):
            fields = {"account": account, "password": password}
            client.action(action, fields)
            client.action("login", fields)
            identity = client.action("session")["user"]
            self.assertEqual(account, identity["account"])
        payload = {
            "title": "数学教材", "description": "无缺页", "price": "29.50",
            "category": "books", "condition": "good", "key": "submit-once",
        }
        item = seller.action("create", payload)["id"]
        seller.action("submit", {"id": item})
        with self.assertRaises(urllib.error.HTTPError) as denied:
            buyer.action("review", {"id": item, "decision": "approve"})
        self.assertEqual(409, denied.exception.code)
        moderator.action("review", {
            "id": item, "decision": "approve", "reason": "图片和描述已核对",
        })
        view = buyer.action("item", {"id": item})
        booking = buyer.action("reserve", {
            "id": item, "price_cents": 2950, "version": view["version"],
            "key": "reserve-once",
        })["id"]
        seller.action("trade", {"id": booking, "action": "accept"})
        seller.action("trade", {"id": booking, "action": "deliver"})
        buyer.action("trade", {"id": booking, "action": "complete"})
        record = buyer.action("records", {"side": "buy"})[0]
        self.assertEqual(("completed", "completed", 2950),
                         (record["state"], record["item_state"],
                          record["price_cents"]))
        buyer.action("logout", {})
        self.assertIsNone(buyer.action("session")["user"])

    def test_local_origin_and_static_ui(self):
        """Reject cross-origin writes and serve the app entry point."""
        client = Client(self.url)
        with self.assertRaises(urllib.error.HTTPError) as denied:
            client.action("setup", {}, "https://elsewhere.invalid")
        self.assertEqual(403, denied.exception.code)
        with client.opener.open(self.url, timeout=10) as response:
            self.assertIn("校园拾光".encode(), response.read())
        self.assertTrue(client.action("session")["needs_admin"])


if __name__ == "__main__":
    unittest.main()
