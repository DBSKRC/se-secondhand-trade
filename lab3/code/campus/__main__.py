"""Initialize the marketplace database and run an interactive terminal."""

import argparse
import getpass
import shlex
import sqlite3
import sys

from campus import auth
from campus import domain
from campus import interface
from campus import output
from campus import storage


def _parse():
    parser = argparse.ArgumentParser(description="校园拾光二手交易终端")
    parser.add_argument("--db", default="data/market.sqlite3", help="数据库路径")
    parser.add_argument("--deadline", type=int, default=86400, help="预约秒数")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--setup-admin", metavar="账号", help="初始化首位管理员")
    args = parser.parse_args()
    if args.deadline < 1:
        parser.error("预约秒数须为正整数")
    return args


def _shell(app, raw):
    print("校园拾光已启动。输入 help 查看命令，quit 退出。")
    with app.trades.expiry_worker():
        while True:
            try:
                line = input("拾光> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line in {"quit", "exit"}:
                break
            if not line:
                continue
            if line == "help":
                app.parser.print_help()
                continue
            try:
                args = shlex.split(line)
                print(output.render(app.execute(args), raw=raw))
            except (domain.RuleError, ValueError, OSError) as error:
                print(f"操作未完成：{error}", file=sys.stderr)
            except sqlite3.Error:
                print("数据库操作失败，请检查文件和连接后重试。", file=sys.stderr)
            except SystemExit:
                # argparse uses SystemExit to finish a help request.
                continue
    app.close_session()


def main():
    """Run the requested local entry point."""
    args = _parse()
    database = storage.Database(args.db)
    try:
        database.initialize()
        if args.setup_admin:
            password = getpass.getpass("首次管理员密码: ")
            repeated = getpass.getpass("再次输入: ")
            if password != repeated:
                raise domain.RuleError("两次输入的密码不一致")
            admin = auth.Accounts(database).bootstrap_admin(
                args.setup_admin, password,
            )
            print(f"管理员已创建，编号 {admin}。")
            return 0
        app = interface.Application(database, args.deadline)
        _shell(app, args.json)
    except (domain.RuleError, OSError, sqlite3.Error) as error:
        print(f"启动失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
