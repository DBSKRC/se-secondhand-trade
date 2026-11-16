"""Password hashing, session tokens, and permission checks."""

import hashlib
import hmac
import secrets

from campus import domain


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 600_000,
    ).hex()


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Accounts:
    """Create accounts and manage expiring sessions."""

    def __init__(self, database):
        self.database = database

    def register(self, account, password):
        """Register a member without granting management permissions."""
        return self._create(account, password, domain.Role.MEMBER)

    def bootstrap_admin(self, account, password):
        """Set up the first administrator at database initialization."""
        return self._create(account, password, domain.Role.ADMIN)

    def _create(self, account, password, role):
        account = domain.account_name(account)
        if not 8 <= len(password) <= 128:
            raise domain.RuleError("密码长度需为 8 至 128 个字符")
        salt = secrets.token_hex(16)
        password_hash = _hash_password(password, salt)
        with self.database.write() as connection:
            if role == domain.Role.ADMIN and connection.execute(
                "SELECT 1 FROM users WHERE role = 'admin'",
            ).fetchone():
                raise domain.RuleError("管理员已初始化")
            if connection.execute(
                "SELECT 1 FROM users WHERE account = ?", (account,),
            ).fetchone():
                raise domain.RuleError("账号已存在")
            cursor = connection.execute(
                """
                INSERT INTO users(account, role, salt, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (account, role, salt, password_hash),
            )
            user_id = cursor.lastrowid
            self.database.audit(
                connection, user_id, "register", "account", user_id,
            )
        return user_id

    def login(self, account, password):
        """Check credentials and issue a token valid for eight hours."""
        account = domain.account_name(account)
        with self.database.connection() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE account = ?", (account,),
            ).fetchone()
        salt = user["salt"] if user else "0" * 32
        expected = user["password_hash"] if user else "0" * 64
        actual = _hash_password(password[:129], salt)
        if not (hmac.compare_digest(actual, expected) and user):
            error = domain.RuleError("账号或密码不正确")
            self.database.denied(None, "login", "account", None, error)
            raise error
        token = secrets.token_urlsafe(32)
        with self.database.write() as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                (_hash_token(token), user["id"], self.database.now() + 28800),
            )
            self.database.audit(
                connection, user["id"], "login", "account", user["id"],
            )
        return token

    def logout(self, token):
        """Invalidate the caller's current session."""
        with self.database.write() as connection:
            user = identify(connection, token, self.database.now())
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?",
                (_hash_token(token),),
            )
            self.database.audit(
                connection, user["id"], "logout", "account", user["id"],
            )


def identify(connection, token, now, role=None):
    """Resolve a live session and optionally enforce a role."""
    if not token:
        raise domain.RuleError("请先登录")
    user = connection.execute(
        """
        SELECT u.id, u.account, u.role
        FROM sessions AS s JOIN users AS u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (_hash_token(token), now),
    ).fetchone()
    if user is None:
        raise domain.RuleError("登录已失效，请重新登录")
    if role is not None and user["role"] != role:
        raise domain.RuleError("当前账号无权执行此操作")
    return user
