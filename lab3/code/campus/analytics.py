"""Read-only business statistics and audit filtering."""

from campus import auth
from campus import commands
from campus import domain


def _time_filter(terms, args, column, start, end):
    if start is not None:
        terms.append(f"{column} >= ?")
        args.append(start)
    if end is not None:
        terms.append(f"{column} < ?")
        args.append(end)


def _check_window(start, end):
    if start is not None and end is not None and end <= start:
        raise domain.RuleError("结束时间须晚于开始时间")


def _group(connection, sql, args, allowed):
    result = dict.fromkeys(allowed, 0)
    for key, count in connection.execute(sql, args):
        result[key] = count
    return result


class Analytics(commands.Service):
    """Provide scoped summaries without changing marketplace data."""

    def summary(self, token, scope, start=None, end=None, category=None,
                state=None):
        """Count by item creation, reservation creation, and completion time."""
        _check_window(start, end)
        if scope not in {"mine", "admin"}:
            raise domain.RuleError("统计范围无效")
        role = "member" if scope == "mine" else "admin"
        with self.database.snapshot() as cx:
            user = auth.identify(cx, token, self.database.now(), role)
            terms, args = self._scope(user["id"] if scope == "mine" else None,
                                      category, state)
            item_terms = list(terms)
            item_args = list(args)
            _time_filter(item_terms, item_args, "i.created_at", start, end)
            item_where = " AND ".join(item_terms)
            items = _group(
                cx,
                f"""
                SELECT i.state, COUNT(*) FROM items AS i
                WHERE {item_where} GROUP BY i.state
                """,
                item_args, domain.ItemState,
            )
            result = {
                "scope": scope,
                "from_inclusive": start,
                "to_exclusive": end,
                "items": sum(items.values()),
                "item_states": items,
                "completed": self._completed(cx, terms, args, start, end),
            }
            if scope == "admin":
                result.update(self._global_counts(cx, terms, args, start, end))
            return result

    @staticmethod
    def _scope(seller, category, state):
        terms = ["1 = 1"]
        args = []
        if seller is not None:
            terms.append("i.seller_id = ?")
            args.append(seller)
        if category:
            terms.append("i.category = ?")
            args.append(domain.choice("分类", category, domain.CATEGORIES))
        if state:
            terms.append("i.state = ?")
            args.append(domain.choice("商品状态", state, tuple(domain.ItemState)))
        return terms, args

    @staticmethod
    def _completed(connection, terms, args, start, end):
        terms = [*terms, "r.state = 'completed'"]
        args = list(args)
        _time_filter(terms, args, "r.completed_at", start, end)
        where = " AND ".join(terms)
        return connection.execute(
            f"""
            SELECT COUNT(*) FROM reservations AS r
            JOIN items AS i ON i.id = r.item_id WHERE {where}
            """,
            args,
        ).fetchone()[0]

    @staticmethod
    def _global_counts(connection, terms, args, start, end):
        reservation_terms = list(terms)
        reservation_args = list(args)
        _time_filter(
            reservation_terms, reservation_args, "r.created_at", start, end,
        )
        where = " AND ".join(reservation_terms)
        reservations = _group(
            connection,
            f"""
            SELECT r.state, COUNT(*) FROM reservations AS r
            JOIN items AS i ON i.id = r.item_id
            WHERE {where} GROUP BY r.state
            """,
            reservation_args, domain.ReservationState,
        )
        report_terms, report_args = list(terms), list(args)
        _time_filter(report_terms, report_args, "p.created_at", start, end)
        where = " AND ".join(report_terms)
        report_total, handled = connection.execute(
            f"""
            SELECT COUNT(*), COUNT(p.handled_at) FROM reports AS p
            JOIN items AS i ON i.id = p.item_id WHERE {where}
            """,
            report_args,
        ).fetchone()
        return {
            "reservations": sum(reservations.values()),
            "valid_reservations": sum(
                count for state, count in reservations.items()
                if state not in {"cancelled", "rejected"}
            ),
            "reservation_states": reservations,
            "reports": report_total,
            "reports_handled": handled,
        }

    def audit_log(self, token, start=None, end=None, actor=None, action=None,
                  entity=None, outcome=None, limit=100, offset=0):
        """List administrator-visible audit records for combined conditions."""
        _check_window(start, end)
        if not 1 <= limit <= 500 or not 0 <= offset <= 1_000_000:
            raise domain.RuleError("日志查询条数或偏移量无效")
        with self.database.snapshot() as cx:
            auth.identify(cx, token, self.database.now(), "admin")
            terms, args = ["1 = 1"], []
            _time_filter(terms, args, "a.created_at", start, end)
            filters = (
                ("u.account", actor), ("a.action", action),
                ("a.entity", entity), ("a.outcome", outcome),
            )
            for column, value in filters:
                if value:
                    terms.append(f"{column} = ?")
                    args.append(value)
            where = " AND ".join(terms)
            rows = cx.execute(
                f"""
                SELECT a.*, u.account FROM audit AS a
                LEFT JOIN users AS u ON u.id = a.actor_id
                WHERE {where} ORDER BY a.id DESC LIMIT ? OFFSET ?
                """,
                (*args, limit, offset),
            )
            return [dict(row) for row in rows]
