"""Define command arguments and map them to marketplace services."""

import argparse
import datetime
import getpass
import pathlib
import uuid

from campus import analytics
from campus import auth
from campus import catalog
from campus import domain
from campus import governance
from campus import maintenance
from campus import trades


class Parser(argparse.ArgumentParser):
    """Keep command errors local to the interactive session."""

    def error(self, message):
        raise domain.RuleError(message)


def _command(group, name, help_text, handler):
    parser = group.add_parser(name, help=help_text)
    parser.set_defaults(handler=handler)
    return parser


def _id(parser, name):
    parser.add_argument(name, type=int, metavar="ID")


def _item_fields(parser):
    parser.add_argument("title", help="商品标题")
    parser.add_argument("description", help="商品描述")
    parser.add_argument("price", help="人民币金额，例如 35.50")
    parser.add_argument(
        "--category", choices=domain.CATEGORIES, default="other",
    )
    parser.add_argument(
        "--condition", choices=domain.CONDITIONS, default="good",
    )


def _window(parser):
    parser.add_argument("--from", dest="start", type=_date)
    parser.add_argument("--until", dest="end", type=_date)


def _date(value):
    try:
        day = datetime.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("日期格式为 YYYY-MM-DD") from error
    midnight = datetime.datetime.combine(
        day, datetime.time.min, tzinfo=datetime.timezone.utc,
    )
    return int(midnight.timestamp())


def _request_key(args):
    return args.request or uuid.uuid4().hex


def _fields(args):
    return catalog.item_payload(
        args.title, args.description, args.category, args.condition, args.price,
    )


def _create_account(app, args):
    password = getpass.getpass("密码: ")
    return {"user_id": app.accounts.register(args.account, password)}


def _login(app, args):
    token = app.accounts.login(args.account, getpass.getpass("密码: "))
    app.close_session()
    app.token = token
    return {"message": f"已登录 {args.account}"}


def _logout(app, _args):
    app.accounts.logout(app.token)
    app.token = None
    return {"message": "已退出登录"}


def _search(app, args):
    minimum = domain.price_cents(args.minimum) if args.minimum else None
    maximum = domain.price_cents(args.maximum) if args.maximum else None
    return app.catalog.search(
        app.token, scope=args.scope, state=args.state, keyword=args.keyword,
        category=args.category, minimum=minimum, maximum=maximum,
        sort=args.sort, page=args.page, size=args.size,
    )


def _detail(app, args):
    return app.catalog.detail(app.token, args.item)


def _create(app, args):
    item = app.catalog.create(
        app.token, _request_key(args), _fields(args), args.image,
    )
    return {"item_id": item}


def _revise(app, args):
    state = app.catalog.revise(app.token, args.item, _fields(args))
    return {"item_id": args.item, "state": state}


def _add_image(app, args):
    position = app.catalog.add_image(app.token, args.item, args.file)
    return {"image_position": position}


def _save_image(app, args):
    contents = app.catalog.image(app.token, args.item, args.position)
    with pathlib.Path(args.output).open("xb") as stream:
        stream.write(contents)
    return {"file": args.output}


def _seller_action(app, args):
    state = app.catalog.seller_action(app.token, args.item, args.item_action)
    return {"item_id": args.item, "state": state}


def _review(app, args):
    state = app.catalog.review(
        app.token, args.item, args.decision == "approve", args.reason,
    )
    return {"item_id": args.item, "state": state}


def _reserve(app, args):
    return app.trades.reserve(
        app.token, args.item, domain.price_cents(args.price), args.version,
        _request_key(args),
    )


def _trade_action(app, args):
    state = app.trades.act(
        app.token, args.booking, args.trade_action, args.reason,
    )
    return {"reservation_id": args.booking, "state": state}


def _records(app, args):
    return app.trades.records(app.token, args.side, args.booking)


def _moderate(app, args):
    state = app.governance.moderate(
        app.token, args.item, args.decision, args.reason,
    )
    return {"item_id": args.item, "state": state}


def _report(app, args):
    report_id = app.governance.submit_report(
        app.token, args.item, args.reason, _request_key(args),
    )
    return {"report_id": report_id}


def _resolve_report(app, args):
    app.governance.resolve_report(
        app.token, args.report, args.result, args.decision, args.reason,
    )
    return {"report_id": args.report, "message": "举报处理已记录"}


def _reports(app, args):
    return app.governance.reports(app.token, args.open)


def _disputes(app, args):
    return app.governance.disputes(app.token, args.dispute)


def _opinion(app, args):
    note = app.governance.add_opinion(app.token, args.dispute, args.opinion)
    return {"note_id": note}


def _stats(app, args):
    return app.analytics.summary(
        app.token, args.scope, args.start, args.end, args.category, args.state,
    )


def _audit(app, args):
    return app.analytics.audit_log(
        app.token, args.start, args.end, args.actor, args.action,
        args.entity, args.outcome, args.limit, args.offset,
    )


def _check(app, _args):
    return app.maintenance.inspect(app.token)


def _backup(app, args):
    return {"file": app.maintenance.backup(app.token, args.output)}


def _accounts(group):
    register = _command(group, "register", "注册普通账号", _create_account)
    register.add_argument("account")
    login = _command(group, "login", "登录", _login)
    login.add_argument("account")
    _command(group, "logout", "退出当前账号", _logout)


def _products(group):
    search = _command(group, "search", "组合查询商品", _search)
    search.add_argument("--scope", choices=["public", "mine", "admin"],
                        default="public")
    search.add_argument("--state", choices=domain.ItemState)
    search.add_argument("--keyword", default="")
    search.add_argument("--category", choices=domain.CATEGORIES)
    search.add_argument("--min", dest="minimum", metavar="金额")
    search.add_argument("--max", dest="maximum", metavar="金额")
    search.add_argument("--sort", choices=["newest", "price-up", "price-down"],
                        default="newest")
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--size", type=int, default=20)
    detail = _command(group, "item", "查看详情或审核原因", _detail)
    _id(detail, "item")
    create = _command(group, "create", "保存商品草稿", _create)
    _item_fields(create)
    create.add_argument("--image", action="append", default=[])
    create.add_argument("--request", help="用于重试的请求编号")
    revise = _command(group, "revise", "修改商品资料", _revise)
    _id(revise, "item")
    _item_fields(revise)
    attach = _command(group, "add-image", "为商品补图", _add_image)
    _id(attach, "item")
    attach.add_argument("file")
    save = _command(group, "save-image", "导出可查看的商品图片", _save_image)
    _id(save, "item")
    save.add_argument("position", type=int)
    save.add_argument("output")
    for action, label in (("submit", "提交审核"), ("withdraw", "卖家下架")):
        parser = _command(group, action, label, _seller_action)
        parser.set_defaults(item_action=action)
        _id(parser, "item")
    review = _command(group, "review", "管理员审核商品", _review)
    _id(review, "item")
    review.add_argument("decision", choices=["approve", "reject"])
    review.add_argument("reason")


def _reservations(group):
    reserve = _command(group, "reserve", "按看到的价格和版本预约", _reserve)
    _id(reserve, "item")
    reserve.add_argument("price", help="确认后的价格（元）")
    reserve.add_argument("version", type=int, help="商品详情中显示的版本")
    reserve.add_argument("--request", help="用于重试的请求编号")
    actions = (
        (domain.Action.ACCEPT, "卖家接受"),
        (domain.Action.CANCEL, "买家取消"),
        (domain.Action.REJECT, "卖家拒绝"),
        (domain.Action.DELIVER, "卖家标记已交付"),
        (domain.Action.COMPLETE, "买家确认完成"),
        (domain.Action.DISPUTE, "买家提出争议"),
    )
    for action, label in actions:
        parser = _command(group, action.value, label, _trade_action)
        parser.set_defaults(trade_action=action)
        _id(parser, "booking")
        if action in {domain.Action.REJECT, domain.Action.DISPUTE}:
            parser.add_argument("reason")
        else:
            parser.set_defaults(reason="")
    records = _command(group, "records", "查询买入或卖出记录", _records)
    records.add_argument("side", choices=["buy", "sell"])
    records.add_argument("--booking", type=int)


def _moderation(group):
    moderate = _command(group, "moderate", "管理员下架或冻结", _moderate)
    _id(moderate, "item")
    moderate.add_argument("decision", choices=["withdraw", "freeze"])
    moderate.add_argument("reason")
    report = _command(group, "report", "举报商品", _report)
    _id(report, "item")
    report.add_argument("reason")
    report.add_argument("--request")
    resolve = _command(group, "resolve-report", "管理员处理举报", _resolve_report)
    _id(resolve, "report")
    resolve.add_argument("result")
    resolve.add_argument("--decision", choices=["withdraw", "freeze"])
    resolve.add_argument("--reason", default="")
    reports = _command(group, "reports", "管理员查看举报", _reports)
    reports.add_argument("--open", action="store_true", help="仅查看未处理举报")
    disputes = _command(group, "disputes", "管理员查看争议与意见", _disputes)
    disputes.add_argument("--dispute", type=int)
    opinion = _command(group, "opinion", "追加争议处理意见", _opinion)
    _id(opinion, "dispute")
    opinion.add_argument("opinion")


def _analytics(group):
    stats = _command(group, "stats", "查询商品和交易统计", _stats)
    stats.add_argument("scope", choices=["mine", "admin"])
    stats.add_argument("--category", choices=domain.CATEGORIES)
    stats.add_argument("--state", choices=domain.ItemState)
    _window(stats)
    audit = _command(group, "audit", "管理员查询操作日志", _audit)
    _window(audit)
    audit.add_argument("--actor")
    audit.add_argument("--action")
    audit.add_argument("--entity")
    audit.add_argument("--outcome", choices=["ok", "denied"])
    audit.add_argument("--limit", type=int, default=100)
    audit.add_argument("--offset", type=int, default=0)
    _command(group, "check", "管理员检查数据一致性", _check)
    backup = _command(group, "backup", "管理员保存数据库备份", _backup)
    backup.add_argument("output", help="新备份文件路径")


def command_parser():
    """Build the command grammar shared by the interactive shell."""
    parser = Parser(prog="校园拾光", description="输入 help 查看可用命令")
    group = parser.add_subparsers(dest="command", required=True)
    _accounts(group)
    _products(group)
    _reservations(group)
    _moderation(group)
    _analytics(group)
    return parser


# Each instance shares one session across its application services.
# pylint: disable-next=too-many-instance-attributes
class Application:
    """Connect interactive commands to a single set of services."""

    def __init__(self, database, deadline):
        self.accounts = auth.Accounts(database)
        self.catalog = catalog.Catalog(database)
        self.trades = trades.Trades(database, deadline)
        self.governance = governance.Governance(database)
        self.analytics = analytics.Analytics(database)
        self.maintenance = maintenance.Maintenance(database)
        self.token = None
        self.parser = command_parser()

    def close_session(self):
        """Revoke the current token, including when switching accounts."""
        if self.token:
            try:
                self.accounts.logout(self.token)
            except domain.RuleError:
                pass
            self.token = None

    def execute(self, arguments):
        """Parse and dispatch one command."""
        self.trades.expire()
        args = self.parser.parse_args(arguments)
        return args.handler(self, args)
