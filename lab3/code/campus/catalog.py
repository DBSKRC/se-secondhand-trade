"""Product editing, image storage, public search, and moderation."""

import hashlib
import pathlib

from campus import auth
from campus import commands
from campus import domain
from campus import storage


def item_payload(title, description, category, condition, price):
    """Validate a complete editable product form."""
    return {
        "title": domain.required("标题", title, 100),
        "description": domain.required("描述", description, 2000),
        "category": domain.choice("分类", category, domain.CATEGORIES),
        "condition": domain.choice("成色", condition, domain.CONDITIONS),
        "price_cents": domain.price_cents(price),
    }


def change_state(connection, item_id, state, now):
    """Change item state and invalidate previously viewed versions."""
    connection.execute(
        """
        UPDATE items SET state = ?, version = version + 1, updated_at = ?
        WHERE id = ?
        """,
        (state, now, item_id),
    )


def _owned(connection, item_id, actor):
    item = storage.fetch(connection, "items", item_id, "商品")
    if item["seller_id"] != actor:
        raise domain.RuleError("只能管理自己的商品")
    return item


def _image_bytes(path):
    source = pathlib.Path(path)
    try:
        with source.open("rb") as stream:
            contents = stream.read(5 * 1024 * 1024 + 1)
    except OSError as error:
        raise domain.RuleError("图片文件无法读取") from error
    if len(contents) > 5 * 1024 * 1024:
        raise domain.RuleError("每张图片最多 5 MB")
    if not contents.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
        raise domain.RuleError("图片文件须为 PNG 或 JPEG")
    return source.name, contents


class Catalog(commands.Service):
    """Manage seller drafts, product detail, and search."""

    def create(self, token, request_key, payload, image_paths=()):
        """Create a draft or replay the same create request."""
        with self.command(token, "member", "create", "item") as (cx, actor):
            if len(image_paths) > 5:
                raise domain.RuleError("每件商品最多上传五张图片")
            images = [_image_bytes(path) for path in image_paths]
            fingerprint = dict(payload)
            fingerprint["images"] = [
                (name, hashlib.sha256(data).hexdigest())
                for name, data in images
            ]

            def create_draft():
                now = self.database.now()
                cursor = cx.execute(
                    """
                    INSERT INTO items(seller_id, title, description, category,
                                      condition, price_cents, state,
                                      created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?)
                    """,
                    (actor, payload["title"], payload["description"],
                     payload["category"], payload["condition"],
                     payload["price_cents"], now, now),
                )
                item_id = cursor.lastrowid
                cx.executemany(
                    "INSERT INTO item_images VALUES (?, ?, ?, ?)",
                    [(item_id, i, name, data)
                     for i, (name, data) in enumerate(images, 1)],
                )
                self.database.audit(
                    cx, actor, "create", "item", item_id, after="draft",
                )
                return item_id

            return storage.once(
                cx, actor, "create_item", request_key, fingerprint,
                create_draft,
            )

    def revise(self, token, item_id, payload):
        """Update an editable item and require review for material changes."""
        with self.command(
            token, "member", "revise", "item", item_id,
        ) as (cx, actor):
            item = _owned(cx, item_id, actor)
            before = item["state"]
            if before not in {"draft", "rejected", "published"}:
                raise domain.RuleError("该状态下不能修改商品，请刷新")
            material = ("title", "description", "category", "price_cents")
            changed = any(item[key] != payload[key] for key in material)
            after = "review" if before == "published" and changed else before
            values = dict(
                payload, state=after, now=self.database.now(), item_id=item_id,
            )
            cx.execute(
                """
                UPDATE items
                SET title = :title, description = :description,
                    category = :category, condition = :condition,
                    price_cents = :price_cents, state = :state,
                    updated_at = :now, version = version + 1
                WHERE id = :item_id
                """,
                values,
            )
            self.database.audit(
                cx, actor, "revise", "item", item_id, before, after,
            )
            return after

    def add_image(self, token, item_id, path):
        """Attach an image while the seller may edit the item."""
        with self.command(
            token, "member", "add_image", "item", item_id,
        ) as (cx, actor):
            item = _owned(cx, item_id, actor)
            if item["state"] not in {"draft", "rejected", "published"}:
                raise domain.RuleError("当前商品不可补图")
            position = cx.execute(
                "SELECT COUNT(*) + 1 FROM item_images WHERE item_id = ?",
                (item_id,),
            ).fetchone()[0]
            if position > 5:
                raise domain.RuleError("每件商品最多上传五张图片")
            name, contents = _image_bytes(path)
            cx.execute(
                "INSERT INTO item_images VALUES (?, ?, ?, ?)",
                (item_id, position, name, contents),
            )
            change_state(cx, item_id, item["state"], self.database.now())
            self.database.audit(cx, actor, "add_image", "item", item_id)
            return position

    def seller_action(self, token, item_id, action):
        """Submit a draft for review or withdraw a published item."""
        transitions = {
            "submit": ({"draft", "rejected"}, "review"),
            "withdraw": ({"published"}, "withdrawn"),
        }
        allowed, after = transitions[action]
        with self.command(
            token, "member", action, "item", item_id,
        ) as (cx, actor):
            item = _owned(cx, item_id, actor)
            before = item["state"]
            if before not in allowed:
                raise domain.RuleError("当前商品状态不允许此操作，请刷新")
            change_state(cx, item_id, after, self.database.now())
            self.database.audit(
                cx, actor, action, "item", item_id, before, after,
            )
            return after

    def review(self, token, item_id, approve, reason):
        """Write an administrator decision and its reason atomically."""
        with self.command(
            token, "admin", "review", "item", item_id,
        ) as (cx, actor):
            item = storage.fetch(cx, "items", item_id, "商品")
            if item["state"] != "review":
                raise domain.RuleError("该商品已不处于待审核状态")
            reason = domain.required("审核原因", reason, 1000)
            after = "published" if approve else "rejected"
            now = self.database.now()
            cx.execute(
                """
                INSERT INTO reviews(item_id, admin_id, decision, reason,
                                    created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item_id, actor, after, reason, now),
            )
            change_state(cx, item_id, after, now)
            self.database.audit(
                cx, actor, "review", "item", item_id, "review", after, reason,
            )
            return after

    def detail(self, token, item_id):
        """Show private item data only to its seller or an administrator."""
        with self.database.snapshot() as cx:
            item, privileged = self._visible(cx, token, item_id)
            result = dict(item)
            result["images"] = [
                dict(row) for row in cx.execute(
                    """
                    SELECT position, filename FROM item_images
                    WHERE item_id = ? ORDER BY position
                    """,
                    (item_id,),
                )
            ]
            if privileged:
                result["reviews"] = [
                    dict(row) for row in cx.execute(
                        """
                        SELECT decision, reason, created_at FROM reviews
                        WHERE item_id = ? ORDER BY id
                        """,
                        (item_id,),
                    )
                ]
            return result

    def image(self, token, item_id, position):
        """Return the original image bytes after checking visibility."""
        with self.database.snapshot() as cx:
            self._visible(cx, token, item_id)
            row = cx.execute(
                """
                SELECT contents FROM item_images
                WHERE item_id = ? AND position = ?
                """,
                (item_id, position),
            ).fetchone()
            if row is None:
                raise domain.RuleError("图片不存在")
            return row["contents"]

    def _visible(self, connection, token, item_id):
        item = storage.fetch(connection, "items", item_id, "商品")
        user = (
            auth.identify(connection, token, self.database.now())
            if token else None
        )
        privileged = user is not None and (
            user["role"] == "admin" or user["id"] == item["seller_id"]
        )
        if item["state"] != "published" and not privileged:
            raise domain.RuleError("商品不可公开查看")
        return item, privileged

    def search(self, token=None, *, scope="public", state=None, keyword="",
               category=None, minimum=None, maximum=None, sort="newest",
               page=1, size=20):
        """Return one stable page of authorized matching items."""
        orders = {
            "newest": "created_at DESC, id DESC",
            "price-up": "price_cents, id",
            "price-down": "price_cents DESC, id",
        }
        if sort not in orders or not 1 <= page <= 1_000_000:
            raise domain.RuleError("排序或页码无效")
        if not 1 <= size <= 100:
            raise domain.RuleError("每页条数须为 1 至 100")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise domain.RuleError("最低价不能高于最高价")
        with self.database.snapshot() as cx:
            terms, args = self._scope(cx, token, scope, state)
            if keyword.strip():
                term = keyword.strip()
                terms.append(
                    "(instr(title, ?) > 0 OR instr(description, ?) > 0)",
                )
                args.extend([term, term])
            if category:
                terms.append("category = ?")
                args.append(domain.choice("分类", category, domain.CATEGORIES))
            for operator, value in ((">=", minimum), ("<=", maximum)):
                if value is not None:
                    terms.append(f"price_cents {operator} ?")
                    args.append(value)
            where = " AND ".join(terms) if terms else "1"
            total = cx.execute(
                f"SELECT COUNT(*) FROM items WHERE {where}", args,
            ).fetchone()[0]
            rows = cx.execute(
                f"""
                SELECT id, seller_id, title, category, condition, price_cents,
                       state, version, created_at
                FROM items WHERE {where}
                ORDER BY {orders[sort]} LIMIT ? OFFSET ?
                """,
                (*args, size, (page - 1) * size),
            )
            return {"total": total, "page": page,
                    "items": [dict(row) for row in rows]}

    def _scope(self, connection, token, scope, state):
        terms = []
        args = []
        if scope == "public":
            terms.append("state = 'published'")
        elif scope == "mine":
            user = auth.identify(
                connection, token, self.database.now(), "member",
            )
            terms.append("seller_id = ?")
            args.append(user["id"])
        elif scope == "admin":
            auth.identify(connection, token, self.database.now(), "admin")
        else:
            raise domain.RuleError("查询范围无效")
        if state:
            terms.append("state = ?")
            args.append(domain.choice("商品状态", state, tuple(domain.ItemState)))
        return terms, args
