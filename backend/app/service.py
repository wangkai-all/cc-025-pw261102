"""查询服务: 计算归因并组装 API 响应。"""
from __future__ import annotations

from datetime import timedelta

from . import db
from .attribution import (
    MODELS,
    UNKNOWN_CHANNEL,
    attribute,
    eligible_identities,
    eligible_touchpoints,
)


def _net(conv, refund_map) -> int:
    return 0 if conv.reversed else conv.gross_cents - refund_map.get(conv.order_id, 0)


def _alloc_json(a) -> dict:
    return {
        "touchpoint_id": a.touchpoint_id,
        "channel": a.channel,
        "weight": f"{a.weight.numerator}/{a.weight.denominator}",
        "weight_float": float(a.weight),
        "cents": a.cents,
    }


def compute_all(con, model: str, lookback_days: int):
    """对全部成交按指定口径归因, 返回 (按成交的结果列表, 渠道汇总)。"""
    touchpoints = db.load_touchpoints(con)
    bindings = db.load_bindings(con)
    conversions = db.load_conversions(con)
    refund_map = db.load_refund_map(con)

    per_order = []
    channel_summary: dict[str, dict] = {}
    for conv in conversions:
        allocs, window = attribute(
            conv, touchpoints, bindings, refund_map.get(conv.order_id, 0), model, lookback_days
        )
        net = _net(conv, refund_map)
        by_channel: dict[str, int] = {}
        for a in allocs:
            by_channel[a.channel] = by_channel.get(a.channel, 0) + a.cents
        per_order.append({
            "order_id": conv.order_id,
            "user_id": conv.user_id,
            "gross_cents": conv.gross_cents,
            "refund_cents": refund_map.get(conv.order_id, 0),
            "net_cents": net,
            "reversed": conv.reversed,
            "ts": conv.ts.isoformat(),
            "touchpoint_count": len(window),
            "by_channel": by_channel,
            "allocations": [_alloc_json(a) for a in allocs],
        })
        for channel, cents in by_channel.items():
            s = channel_summary.setdefault(channel, {"channel": channel, "net_cents": 0, "orders": 0})
            s["net_cents"] += cents
            if cents != 0:
                s["orders"] += 1
    summary = sorted(channel_summary.values(), key=lambda s: -s["net_cents"])
    total_net = sum(o["net_cents"] for o in per_order)
    assert sum(s["net_cents"] for s in summary) == total_net, "渠道合计必须等于成交净额合计"
    return per_order, summary, total_net


def conversion_detail(con, order_id: str, model: str, lookback_days: int) -> dict | None:
    touchpoints = db.load_touchpoints(con)
    bindings = db.load_bindings(con)
    conversions = {c.order_id: c for c in db.load_conversions(con)}
    conv = conversions.get(order_id)
    if conv is None:
        return None
    refund_map = db.load_refund_map(con)
    allocs, window = attribute(
        conv, touchpoints, bindings, refund_map.get(order_id, 0), model, lookback_days
    )
    alloc_by_tp = {a.touchpoint_id: a for a in allocs}
    idents = eligible_identities(conv, bindings)
    window_ids = {t.touchpoint_id for t in window}
    window_start = conv.ts - timedelta(days=lookback_days)

    # 与该用户有关(曾经绑定过)的全部触点, 标注纳入/排除原因
    related_anons = {b.anon_id for b in bindings if b.user_id == conv.user_id}
    path = []
    for t in sorted(
        (t for t in touchpoints if t.anon_id in related_anons),
        key=lambda t: (t.ts, t.touchpoint_id),
    ):
        if t.touchpoint_id in alloc_by_tp:
            status = "credited"
        elif t.touchpoint_id in window_ids:
            status = "in_window_not_credited"
        elif t.anon_id not in idents:
            status = "binding_after_conversion"
        elif t.ts > conv.ts:
            status = "after_conversion"
        else:
            status = "outside_window"
        a = alloc_by_tp.get(t.touchpoint_id)
        path.append({
            "touchpoint_id": t.touchpoint_id,
            "anon_id": t.anon_id,
            "channel": t.channel,
            "is_direct": t.is_direct,
            "ts": t.ts.isoformat(),
            "status": status,
            "weight": (f"{a.weight.numerator}/{a.weight.denominator}" if a else None),
            "cents": (a.cents if a else 0),
        })

    return {
        "order": {
            "order_id": conv.order_id,
            "user_id": conv.user_id,
            "gross_cents": conv.gross_cents,
            "refund_cents": refund_map.get(order_id, 0),
            "net_cents": _net(conv, refund_map),
            "reversed": conv.reversed,
            "ts": conv.ts.isoformat(),
        },
        "refunds": db.load_refunds_for(con, order_id),
        "window": {"start": window_start.isoformat(), "end": conv.ts.isoformat(), "days": lookback_days},
        "bindings": [
            {
                "anon_id": b.anon_id,
                "bound_at": b.bound_at.isoformat(),
                "usable": b.bound_at <= conv.ts,
            }
            for b in sorted(bindings, key=lambda b: b.bound_at)
            if b.user_id == conv.user_id
        ],
        "touchpoints": path,
        "allocations": [_alloc_json(a) for a in allocs],
        "unknown_channel": UNKNOWN_CHANNEL,
    }


def compare(con, lookback_days: int) -> dict:
    """三种口径下每笔成交的渠道分摊, 用于对比哪些成交造成渠道金额变化。"""
    touchpoints = db.load_touchpoints(con)
    bindings = db.load_bindings(con)
    conversions = db.load_conversions(con)
    refund_map = db.load_refund_map(con)
    orders = []
    for conv in conversions:
        by_model = {}
        for model in MODELS:
            allocs, _ = attribute(
                conv, touchpoints, bindings, refund_map.get(conv.order_id, 0), model, lookback_days
            )
            by_channel: dict[str, int] = {}
            for a in allocs:
                by_channel[a.channel] = by_channel.get(a.channel, 0) + a.cents
            by_model[model] = by_channel
        orders.append({
            "order_id": conv.order_id,
            "user_id": conv.user_id,
            "ts": conv.ts.isoformat(),
            "net_cents": _net(conv, refund_map),
            "by_model": by_model,
        })
    return {"models": MODELS, "orders": orders}
