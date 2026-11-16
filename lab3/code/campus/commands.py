"""Common transaction and audit boundary for application services."""

import contextlib

from campus import auth
from campus import domain


class Service:
    """Provide consistent authentication and command handling."""

    def __init__(self, database):
        self.database = database

    @contextlib.contextmanager
    def command(self, token, role, action, entity, entity_id=None):
        """Start a write, authenticate, and audit rejected commands."""
        actor = None
        try:
            with self.database.write() as connection:
                user = auth.identify(connection, token, self.database.now())
                actor = user["id"]
                if role is not None and user["role"] != role:
                    raise domain.RuleError("当前账号无权执行此操作")
                yield connection, actor
        except domain.RuleError as error:
            self.database.denied(actor, action, entity, entity_id, error)
            raise
