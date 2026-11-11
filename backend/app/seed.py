"""演示数据: 覆盖跨日触点、成交后身份绑定、三方平分一分钱、部分退款、
撤销成交、同时间触点按编号排序、仅直接访问、无触点未知来源、重复导入幂等。
"""
from . import db

TOUCHPOINTS = [
    # 场景1 跨日触点: U1 在 10-30 有一次小红书触点, 7 天窗口看不到, 30 天窗口能看到
    {"touchpoint_id": 1, "anon_id": "A1", "channel": "小红书", "is_direct": False, "ts": "2026-10-30T10:00:00"},
    {"touchpoint_id": 2, "anon_id": "A1", "channel": "搜索引擎SEM", "is_direct": False, "ts": "2026-11-06T10:00:00"},
    # 场景2 成交后才绑定身份: A2 的朋友圈触点发生在成交 O2a 之前, 但绑定在成交之后
    {"touchpoint_id": 3, "anon_id": "A2", "channel": "朋友圈广告", "is_direct": False, "ts": "2026-11-02T09:00:00"},
    {"touchpoint_id": 4, "anon_id": "A2", "channel": "直接访问", "is_direct": True, "ts": "2026-11-05T09:00:00"},
    # 场景3 三方平分一分钱
    {"touchpoint_id": 5, "anon_id": "A3", "channel": "小红书", "is_direct": False, "ts": "2026-11-05T08:00:00"},
    {"touchpoint_id": 6, "anon_id": "A3", "channel": "朋友圈广告", "is_direct": False, "ts": "2026-11-05T09:00:00"},
    {"touchpoint_id": 7, "anon_id": "A3", "channel": "搜索引擎SEM", "is_direct": False, "ts": "2026-11-05T10:00:00"},
    # 场景4 部分退款: 两个非直接 + 一个直接
    {"touchpoint_id": 8, "anon_id": "A4", "channel": "小红书", "is_direct": False, "ts": "2026-11-04T14:00:00"},
    {"touchpoint_id": 9, "anon_id": "A4", "channel": "搜索引擎SEM", "is_direct": False, "ts": "2026-11-04T15:00:00"},
    {"touchpoint_id": 10, "anon_id": "A4", "channel": "直接访问", "is_direct": True, "ts": "2026-11-04T15:30:00"},
    # 场景5 撤销成交
    {"touchpoint_id": 11, "anon_id": "A5", "channel": "朋友圈广告", "is_direct": False, "ts": "2026-11-03T10:00:00"},
    # 场景6 同一时刻两个触点, 编号 12 < 13, 首次触达应取 12(小红书)
    {"touchpoint_id": 13, "anon_id": "A6", "channel": "搜索引擎SEM", "is_direct": False, "ts": "2026-11-02T10:00:00"},
    {"touchpoint_id": 12, "anon_id": "A6", "channel": "小红书", "is_direct": False, "ts": "2026-11-02T10:00:00"},
    # 场景8 仅直接访问 -> 末次非直接回退到直接访问
    {"touchpoint_id": 14, "anon_id": "A8", "channel": "直接访问", "is_direct": True, "ts": "2026-11-05T10:00:00"},
]

BINDINGS = [
    {"anon_id": "A1", "user_id": "U1", "bound_at": "2026-10-30T09:00:00"},
    # 关键: A2 -> U2 的绑定发生在成交 O2a(11-03 09:00) 之后
    {"anon_id": "A2", "user_id": "U2", "bound_at": "2026-11-04T09:00:00"},
    {"anon_id": "A3", "user_id": "U3", "bound_at": "2026-11-05T07:00:00"},
    {"anon_id": "A4", "user_id": "U4", "bound_at": "2026-11-04T13:00:00"},
    {"anon_id": "A5", "user_id": "U5", "bound_at": "2026-11-03T09:00:00"},
    {"anon_id": "A6", "user_id": "U6", "bound_at": "2026-11-02T09:00:00"},
    {"anon_id": "A8", "user_id": "U8", "bound_at": "2026-11-05T09:00:00"},
]

CONVERSIONS = [
    {"order_id": "O1", "user_id": "U1", "gross_cents": 10000, "ts": "2026-11-08T10:00:00"},
    # O2a 成交时 A2 尚未绑定 -> 归未知来源
    {"order_id": "O2a", "user_id": "U2", "gross_cents": 5000, "ts": "2026-11-03T09:00:00"},
    # O2b 成交时绑定已建立 -> 可以看到朋友圈广告 + 直接访问
    {"order_id": "O2b", "user_id": "U2", "gross_cents": 8000, "ts": "2026-11-06T09:00:00"},
    {"order_id": "O3", "user_id": "U3", "gross_cents": 1, "ts": "2026-11-05T11:00:00"},
    {"order_id": "O4", "user_id": "U4", "gross_cents": 10000, "ts": "2026-11-04T16:00:00"},
    {"order_id": "O5", "user_id": "U5", "gross_cents": 7000, "ts": "2026-11-03T12:00:00", "reversed": True},
    {"order_id": "O6", "user_id": "U6", "gross_cents": 3000, "ts": "2026-11-02T11:00:00"},
    # 完全无触点 -> 未知来源
    {"order_id": "O7", "user_id": "U7", "gross_cents": 4500, "ts": "2026-11-07T12:00:00"},
    {"order_id": "O8", "user_id": "U8", "gross_cents": 2000, "ts": "2026-11-05T12:00:00"},
]

REFUNDS = [
    {"refund_id": "R1", "order_id": "O4", "amount_cents": 4000, "ts": "2026-11-05T10:00:00"},
]


def seed(con) -> dict:
    """导入演示数据。故意导入两遍, 验证重复导入不累加。"""
    for _ in range(2):
        db.import_touchpoints(con, TOUCHPOINTS)
        db.import_bindings(con, BINDINGS)
        db.import_conversions(con, CONVERSIONS)
        db.import_refunds(con, REFUNDS)
    return db.counts(con)
