"""Output formatting for the terminal and scripted demonstrations."""

import datetime
import json

_LABELS = {
    "id": "编号",
    "state": "状态",
    "item_state": "商品状态",
    "before_state": "操作前状态",
    "after_state": "操作后状态",
    "title": "商品",
    "price_cents": "价格",
    "description": "描述",
    "category": "分类",
    "condition": "成色",
    "version": "版本",
    "seller_id": "卖家编号",
    "buyer_id": "买家编号",
    "item_id": "商品编号",
    "reservation_id": "预约编号",
    "report_id": "举报编号",
    "user_id": "账号编号",
    "actor_id": "操作者编号",
    "account": "账号",
    "closed_reason": "关闭原因",
    "images": "图片",
    "reviews": "审核历史",
    "reason": "原因",
    "result": "处理结果",
    "opinions": "处理意见",
    "total": "匹配总数",
    "page": "页码",
    "items": "商品",
    "item_states": "商品状态分布",
    "completed": "完成交易",
    "reservations": "预约总数",
    "valid_reservations": "有效预约",
    "reservation_states": "预约状态分布",
    "reports": "举报数量",
    "reports_handled": "已处理举报",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "expires_at": "截止时间",
    "completed_at": "完成时间",
    "handled_at": "处理时间",
    "message": "结果",
    "position": "图片序号",
    "filename": "文件名",
    "image_position": "图片序号",
    "file": "文件",
    "note_id": "意见编号",
    "body": "意见",
    "action": "操作",
    "entity": "对象类型",
    "entity_id": "对象编号",
    "outcome": "结果",
    "detail": "详情",
    "from_inclusive": "范围起点（含）",
    "to_exclusive": "范围终点（不含）",
}
_STATES = {
    "draft": "草稿",
    "review": "待审核",
    "published": "已发布",
    "reserved": "已预约",
    "pending": "待卖家确认",
    "cancelled": "已取消",
    "trading": "交易中",
    "delivered": "待买家确认",
    "completed": "已完成",
    "withdrawn": "已下架",
    "frozen": "违规冻结",
    "disputed": "待管理员处理",
    "open": "待处理",
    "handled": "已处理",
}
_TIMES = {
    "created_at", "updated_at", "expires_at", "completed_at", "handled_at",
    "from_inclusive", "to_exclusive",
}


def _state_label(state, reservation):
    if state == "rejected":
        return "已拒绝" if reservation else "审核驳回"
    return _STATES.get(state, state)


def _format_value(key, value, reservation):
    if value is None:
        return "—"
    if key == "price_cents":
        whole, cents = divmod(value, 100)
        return f"¥{whole}.{cents:02d}"
    if key in _TIMES:
        return datetime.datetime.fromtimestamp(
            value, tz=datetime.timezone.utc,
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
    state_fields = {"state", "item_state", "before_state", "after_state",
                    "decision"}
    if key in state_fields:
        return _state_label(value, reservation and key != "item_state")
    if key == "outcome":
        return {"ok": "成功", "denied": "拒绝"}.get(value, value)
    return str(value)


def _format_record(record, indent=0):
    reservation = "buyer_id" in record or record.get("entity") == "reservation"
    prefix = " " * indent
    lines = []
    for key, value in record.items():
        label = _LABELS.get(key, key)
        if isinstance(value, list):
            lines.append(f"{prefix}{label} ({len(value)}):")
            for row in value:
                lines.extend(_format_record(row, indent + 2))
                lines.append("")
        elif isinstance(value, dict):
            lines.append(f"{prefix}{label}:")
            for name, count in value.items():
                state = _state_label(name, key == "reservation_states")
                lines.append(f"{prefix}  {state} {count}")
        else:
            formatted = _format_value(key, value, reservation)
            lines.append(f"{prefix}{label}: {formatted}")
    return lines


def render(result, raw=False):
    """Render an ordered response as readable text or JSON."""
    if result is None:
        return "操作成功"
    if raw:
        return json.dumps(result, ensure_ascii=False, indent=2)
    if isinstance(result, list):
        if not result:
            return "没有匹配记录"
        return "\n\n".join("\n".join(_format_record(row)) for row in result)
    return "\n".join(_format_record(result)).rstrip()
