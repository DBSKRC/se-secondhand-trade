"""Exercise REQ-021 and REQ-022 using a disposable SQLite dataset."""

import concurrent.futures
import json
import pathlib
import platform
import tempfile
import threading
import time

from campus import auth
from campus import catalog
from campus import domain
from campus import storage
from campus import trades


def fixture(database):
    """Load deterministic published items and three authorized actors."""
    accounts = auth.Accounts(database)
    credentials = {}
    for name in ("seller", "buyer_one", "buyer_two"):
        user = accounts.register(name, "fixture-password")
        credentials[name] = (user, accounts.login(name, "fixture-password"))
    seller_id = credentials["seller"][0]
    now = database.now()
    records = [
        (seller_id, f"benchmark-{index:05d}", "fixture",
         "books" if index % 2 == 0 else "daily", "good", index, now, now)
        for index in range(1, 10_001)
    ]
    with database.write() as cx:
        cx.executemany(
            """
            INSERT INTO items(seller_id, title, description, category,
                              condition, price_cents, created_at, updated_at,
                              state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'published')
            """,
            records,
        )
    return credentials


def query_load(service):
    """Group 100 concurrent reads into five groups of 20 workers."""
    expected = list(range(200, 240, 2))

    def query(_):
        started = time.perf_counter()
        result = service.search(
            keyword="benchmark", category="books", minimum=200,
            maximum=300, sort="price-up", page=1, size=20,
        )
        elapsed = time.perf_counter() - started
        actual = [row["price_cents"] for row in result["items"]]
        correct = actual == expected and result["total"] == 51
        return elapsed, correct

    samples = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        for _ in range(5):
            gate = threading.Barrier(20)

            def concurrent_query(index, barrier=gate):
                barrier.wait(timeout=20)
                return query(index)

            samples.extend(pool.map(concurrent_query, range(20)))
    within_budget = sum(seconds <= 1 and valid for seconds, valid in samples)
    return {
        "queries": len(samples),
        "workers": 20,
        "correct": sum(valid for _, valid in samples),
        "correct_within_one_second": within_budget,
        "max_ms": round(max(t for t, _ in samples) * 1000, 2),
        "filter": {
            "category": "books", "minimum_cents": 200, "maximum_cents": 300,
            "sort": "price-up", "page": 1, "size": 20,
        },
    }


def reservation_load(database, service, buyers):
    """Contest 100 different items and verify the stored states."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for item in range(1, 101):
            barrier = threading.Barrier(2)

            def reserve(token, target=item, gate=barrier):
                gate.wait(timeout=10)
                try:
                    service.reserve(token, target, target, 1, f"round-{target}")
                    return True
                except domain.RuleError as error:
                    if "已被预约" not in str(error):
                        raise
                    return False

            if sum(pool.map(reserve, buyers)) != 1:
                raise AssertionError(f"unexpected number of winners for {item}")
    with database.connection() as cx:
        reserved = cx.execute(
            """
            SELECT COUNT(*) FROM items AS i JOIN reservations AS r
              ON r.item_id = i.id
            WHERE i.id <= 100 AND i.state = 'reserved'
              AND r.state = 'pending' AND r.price_cents = i.price_cents
            """,
        ).fetchone()[0]
        total = cx.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
    if (reserved, total) != (100, 100):
        raise AssertionError((reserved, total))
    return {"rounds": 100, "attempts_per_round": 2, "consistent": reserved}


def main():
    """Print measured results and fail on an unmet threshold."""
    with tempfile.TemporaryDirectory() as directory:
        database = storage.Database(pathlib.Path(directory) / "load.db")
        database.initialize()
        actors = fixture(database)
        search = query_load(catalog.Catalog(database))
        buyers = [actors[name][1] for name in ("buyer_one", "buyer_two")]
        reservation = reservation_load(
            database, trades.Trades(database), buyers,
        )
    print(json.dumps({
        "environment": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "items": 10_000,
        "search": search,
        "reservation": reservation,
    }, indent=2))
    return 0 if search["correct_within_one_second"] >= 95 else 1


if __name__ == "__main__":
    raise SystemExit(main())
