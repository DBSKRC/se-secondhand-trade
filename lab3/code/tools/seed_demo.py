"""Create a disposable marketplace for visual demonstrations."""

import argparse
import pathlib
import tempfile

from campus import auth
from campus import catalog
from campus import storage

DEMO_PASSWORD = "campus-demo-2026"
PRODUCTS = (
    ("算法教材", "书角有轻微磨损，无缺页。可在校内面交。", "books", "28", "book.jpg"),
    ("无线鼠标", "无线鼠标一只，功能正常。", "electronics", "39", "mouse.jpg"),
    ("蓝牙耳机", "自用耳机，附充电盒。", "electronics", "88", "earbuds.jpg"),
    ("便携电源", "附原装充电线。", "electronics", "45", "power.jpg"),
    ("随行水杯", "闲置水杯，已清洁。", "daily", "16", "cup.jpg"),
    ("加缪文集", "阅读过一次，书页完整。", "books", "24", "camus.jpg"),
)


def populate(path):
    """Seed users, an administrator, and reviewed products."""
    database = storage.Database(path)
    database.initialize()
    accounts = auth.Accounts(database)
    accounts.bootstrap_admin("moderator", DEMO_PASSWORD)
    accounts.register("seller", DEMO_PASSWORD)
    accounts.register("buyer", DEMO_PASSWORD)
    moderator = accounts.login("moderator", DEMO_PASSWORD)
    seller = accounts.login("seller", DEMO_PASSWORD)
    market = catalog.Catalog(database)
    photos = pathlib.Path(catalog.__file__).with_name("mobile_ui") / "assets"
    for index, (title, text, category, price, image) in enumerate(PRODUCTS):
        fields = catalog.item_payload(title, text, category, "good", price)
        item = market.create(seller, f"demo-{index}", fields, [photos / image])
        market.seller_action(seller, item, "submit")
        market.review(moderator, item, True, "商品信息已核对")
    accounts.logout(seller)
    accounts.logout(moderator)
    with database.connection() as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def main():
    """Use a separate database to preserve a student's own data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=pathlib.Path, default="data/visual-demo.db",
    )
    options = parser.parse_args()
    path = pathlib.Path(options.db).resolve()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as directory:
            candidate = pathlib.Path(directory) / "seed.db"
            populate(candidate)
            candidate.rename(path)
    print("Demo accounts: buyer, seller, moderator")
    print(f"Demo password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
