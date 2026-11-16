"""Marketplace states, values, and validation."""

import enum
import re


class RuleError(Exception):
    """A rejected operation with a message suitable for the caller."""


class Role(enum.StrEnum):
    """Account permissions."""

    MEMBER = "member"
    ADMIN = "admin"


class ItemState(enum.StrEnum):
    """The nine item lifecycle states."""

    DRAFT = "draft"
    REVIEW = "review"
    REJECTED = "rejected"
    PUBLISHED = "published"
    RESERVED = "reserved"
    TRADING = "trading"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    FROZEN = "frozen"


class ReservationState(enum.StrEnum):
    """Reservation lifecycle states."""

    PENDING = "pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    TRADING = "trading"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    DISPUTED = "disputed"


class Action(enum.StrEnum):
    """Commands applicable to a reservation."""

    ACCEPT = "accept"
    CANCEL = "cancel"
    REJECT = "reject"
    DELIVER = "deliver"
    COMPLETE = "complete"
    DISPUTE = "dispute"


# Expected reservation state, actor, next reservation and item states.
TRANSITIONS = {
    Action.ACCEPT: ("pending", "seller", "trading", "trading"),
    Action.CANCEL: ("pending", "buyer", "cancelled", "published"),
    Action.REJECT: ("pending", "seller", "rejected", "published"),
    Action.DELIVER: ("trading", "seller", "delivered", "trading"),
    Action.COMPLETE: ("delivered", "buyer", "completed", "completed"),
    Action.DISPUTE: ("delivered", "buyer", "disputed", "trading"),
}
CLOSED = frozenset({"cancelled", "rejected", "completed"})
CATEGORIES = ("books", "electronics", "daily", "sports", "other")
CONDITIONS = ("new", "like-new", "good", "fair")


def required(label: str, value: str, limit: int) -> str:
    """Return trimmed nonempty text with a maximum length."""
    value = value.strip()
    if not value:
        raise RuleError(f"{label}不能为空")
    if len(value) > limit:
        raise RuleError(f"{label}最多允许 {limit} 个字符")
    return value


def choice(label: str, value: str, options: tuple) -> str:
    """Validate an option against the configured values."""
    if value not in options:
        raise RuleError(f"{label}必须为 {', '.join(options)} 之一")
    return value


def price_cents(value: str) -> int:
    """Parse base-ten yuan without floating-point rounding."""
    if not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,2})?", value.strip()):
        raise RuleError("价格须为非负金额，整数最多十位，小数最多两位")
    whole, _, fraction = value.strip().partition(".")
    return 100 * int(whole) + int(fraction.ljust(2, "0"))


def account_name(value: str) -> str:
    """Normalize and validate a login identifier."""
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,32}", value):
        raise RuleError("账号需为 3 至 32 位字母、数字或下划线")
    return value
