"""Same-origin mobile API backed by the existing marketplace services."""

import base64
import binascii
import datetime
import pathlib
import tempfile

from campus import auth
from campus import catalog
from campus import domain
from campus import interface


# Each public operation implements one API route.
# pylint: disable-next=too-many-public-methods
class Api:
    """Dispatch JSON requests using an independent token for each caller."""

    def __init__(self, database, deadline=86400):
        self.database = database
        self.services = interface.Application(database, deadline)
        self._actions = {
            "register": self.register,
            "setup": self.setup,
            "login": self.login,
            "logout": self.logout,
            "search": self.search,
            "item": self.item,
            "create": self.create,
            "revise": self.revise,
            "submit": self.submit,
            "withdraw": self.withdraw,
            "review": self.review,
            "reserve": self.reserve,
            "trade": self.trade,
            "records": self.records,
            "report": self.report,
            "reports": self.reports,
            "resolve": self.resolve,
            "moderate": self.moderate,
            "disputes": self.disputes,
            "opinion": self.opinion,
            "stats": self.stats,
            "audit": self.audit,
        }

    def call(self, token, action, data):
        """Execute an allowlisted operation."""
        operation = self._actions.get(action)
        if operation is None:
            raise domain.RuleError("未知操作")
        return operation(token, data)

    def session(self, token):
        """Return the identity and whether local setup is needed."""
        with self.database.connection() as connection:
            admin = connection.execute(
                "SELECT 1 FROM users WHERE role = 'admin'",
            ).fetchone()
            user = None
            if token:
                try:
                    user = dict(auth.identify(
                        connection, token, self.database.now(),
                    ))
                except domain.RuleError:
                    pass
            return {"user": user, "needs_admin": admin is None}

    def register(self, _token, data):
        """Create a member."""
        account, password = _credentials(data)
        return {"id": self.services.accounts.register(account, password)}

    def setup(self, _token, data):
        """Bootstrap the local administrator once."""
        account, password = _credentials(data)
        return {"id": self.services.accounts.bootstrap_admin(
            account, password,
        )}

    def login(self, token, data):
        """Return a new token for the HTTP layer to place in a cookie."""
        account, password = _credentials(data)
        updated = self.services.accounts.login(account, password)
        self.logout(token, {})
        return {"session_token": updated}

    def logout(self, token, _data):
        """Revoke the current token, even when a cookie has expired."""
        if token:
            try:
                self.services.accounts.logout(token)
            except domain.RuleError:
                pass
        return {"session_token": ""}

    def search(self, token, data):
        """Search within the public, seller, or administrator scope."""
        low = _text(data, "min")
        high = _text(data, "max")
        return self.services.catalog.search(
            token, scope=_text(data, "scope", "public"),
            state=_text(data, "state"), keyword=_text(data, "keyword"),
            category=_text(data, "category"),
            minimum=domain.price_cents(low) if low else None,
            maximum=domain.price_cents(high) if high else None,
            sort=_text(data, "sort", "newest"),
            page=_integer(data, "page", 1), size=16,
        )

    def item(self, token, data):
        """Get a product and its permitted details."""
        return self.services.catalog.detail(token, _integer(data, "id"))

    def image(self, token, item_id, position):
        """Read an existing product image through the catalog service."""
        return self.services.catalog.image(token, item_id, position)

    def create(self, token, data):
        """Create a draft and store any attached images."""
        payload = _product(data)
        images = data.get("images", [])
        if not isinstance(images, list) or len(images) > 5:
            raise domain.RuleError("每件商品最多上传五张图片")
        with tempfile.TemporaryDirectory() as directory:
            paths = [_save_image(directory, index, image)
                     for index, image in enumerate(images, 1)]
            item_id = self.services.catalog.create(
                token, _text(data, "key"), payload, paths,
            )
        return {"id": item_id}

    def revise(self, token, data):
        """Apply editable fields to an existing listing."""
        return {"state": self.services.catalog.revise(
            token, _integer(data, "id"), _product(data),
        )}

    def submit(self, token, data):
        """Send a draft to administrators."""
        return {"state": self.services.catalog.seller_action(
            token, _integer(data, "id"), "submit",
        )}

    def withdraw(self, token, data):
        """Take down the caller's published product."""
        return {"state": self.services.catalog.seller_action(
            token, _integer(data, "id"), "withdraw",
        )}

    def review(self, token, data):
        """Approve or reject a submitted product."""
        decision = domain.choice(
            "审核结论", _text(data, "decision"), ("approve", "reject"),
        )
        return {"state": self.services.catalog.review(
            token, _integer(data, "id"), decision == "approve",
            _text(data, "reason"),
        )}

    def reserve(self, token, data):
        """Confirm the price and version shown in the buyer's detail page."""
        self.services.trades.expire()
        return self.services.trades.reserve(
            token, _integer(data, "id"), _integer(data, "price_cents"),
            _integer(data, "version"), _text(data, "key"),
        )

    def trade(self, token, data):
        """Perform an allowed buyer or seller action."""
        self.services.trades.expire()
        return {"state": self.services.trades.act(
            token, _integer(data, "id"), _text(data, "action"),
            _text(data, "reason"),
        )}

    def records(self, token, data):
        """Show the caller's reservation history."""
        return self.services.trades.records(token, _text(data, "side", "buy"))

    def report(self, token, data):
        """Submit a reason for a report."""
        return {"id": self.services.governance.submit_report(
            token, _integer(data, "id"), _text(data, "reason"),
            _text(data, "key"),
        )}

    def reports(self, token, _data):
        """List reports for administrative review."""
        return self.services.governance.reports(token)

    def resolve(self, token, data):
        """Resolve a report and optionally take a moderation action."""
        self.services.governance.resolve_report(
            token, _integer(data, "id"), _text(data, "result"),
            _text(data, "decision"), _text(data, "reason"),
        )
        return {"saved": True}

    def moderate(self, token, data):
        """Withdraw or freeze an item."""
        return {"state": self.services.governance.moderate(
            token, _integer(data, "id"), _text(data, "decision"),
            _text(data, "reason"),
        )}

    def disputes(self, token, _data):
        """List disputes and processing history."""
        return self.services.governance.disputes(token)

    def opinion(self, token, data):
        """Append an administrator's handling opinion."""
        return {"id": self.services.governance.add_opinion(
            token, _integer(data, "id"), _text(data, "opinion"),
        )}

    def stats(self, token, data):
        """Get role-scoped counters for the chosen interval."""
        return self.services.analytics.summary(
            token, _text(data, "scope", "mine"),
            _day(data, "start"), _day(data, "end"),
            _text(data, "category"), _text(data, "state"),
        )

    def audit(self, token, data):
        """Read the audit trail for the selected conditions."""
        return self.services.analytics.audit_log(
            token, start=_day(data, "start"), end=_day(data, "end"),
            actor=_text(data, "actor"), action=_text(data, "action"),
            entity=_text(data, "entity"), outcome=_text(data, "outcome"),
        )


def _text(data, key, default=""):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise domain.RuleError(f"字段 {key} 须为文本")
    return value


def _integer(data, key, default=None):
    value = data.get(key, default)
    if (not isinstance(value, int) or isinstance(value, bool)
            or not 0 <= value <= 9_223_372_036_854_775_807):
        raise domain.RuleError(f"字段 {key} 须为有效整数")
    return value


def _credentials(data):
    return _text(data, "account"), _text(data, "password")


def _product(data):
    return catalog.item_payload(
        _text(data, "title"), _text(data, "description"),
        _text(data, "category"), _text(data, "condition"),
        _text(data, "price"),
    )


def _day(data, key):
    value = _text(data, key)
    if not value:
        return None
    try:
        day = datetime.date.fromisoformat(value)
    except ValueError as error:
        raise domain.RuleError("日期须为 YYYY-MM-DD") from error
    combined = datetime.datetime.combine(
        day, datetime.time.min, tzinfo=datetime.timezone.utc,
    )
    return int(combined.timestamp())


def _save_image(directory, index, image):
    if not isinstance(image, str) or len(image) > 7_000_000:
        raise domain.RuleError("每张图片最多 5 MB")
    try:
        payload = base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError) as error:
        raise domain.RuleError("图片数据无效") from error
    path = pathlib.Path(directory) / f"photo-{index}"
    path.write_bytes(payload)
    return path
