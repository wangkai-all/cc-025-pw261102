"""归因引擎核心规则。

规则要点:
- 只使用成交前(含同一时刻)且落在回看窗口内的触点。
- 身份绑定只使用成交时已经建立的关系(bound_at <= 成交时间),
  不允许用后来的登录把过去的匿名访问强行串到成交上。
- 触点排序: 时间升序, 相同时间按触点编号(固定 id)升序。
- 末次非直接: 优先窗口内最后一个非直接渠道; 没有非直接时取最后一个直接访问;
  完全没有触点 -> 未知来源。
- 金额以分为单位; 线性分摊用最大余数法, 余数按小数余数大小降序、
  再按触点编号升序分配, 保证渠道合计回到成交净额。
- 撤销的成交净额归零; 部分退款后按原权重分摊净额。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction

MODEL_FIRST = "first_touch"
MODEL_LAST_NON_DIRECT = "last_non_direct"
MODEL_LINEAR = "linear"
MODELS = [MODEL_FIRST, MODEL_LAST_NON_DIRECT, MODEL_LINEAR]
MODEL_LABELS = {
    MODEL_FIRST: "首次触达",
    MODEL_LAST_NON_DIRECT: "末次非直接触达",
    MODEL_LINEAR: "线性分摊",
}
UNKNOWN_CHANNEL = "未知来源"


@dataclass(frozen=True)
class Touchpoint:
    touchpoint_id: int
    anon_id: str
    channel: str
    is_direct: bool
    ts: datetime


@dataclass(frozen=True)
class Binding:
    anon_id: str
    user_id: str
    bound_at: datetime


@dataclass(frozen=True)
class Conversion:
    order_id: str
    user_id: str
    gross_cents: int
    ts: datetime
    reversed: bool


@dataclass(frozen=True)
class Allocation:
    touchpoint_id: int | None  # None 表示未知来源
    channel: str
    weight: Fraction
    cents: int


def allocate_cents(net_cents: int, weighted_ids: list[tuple[int, int]]) -> dict[int, int]:
    """最大余数法把 net_cents(分) 按权重分摊到触点。

    weighted_ids: [(touchpoint_id, weight)], id 必须唯一。
    余数按小数余数降序、再按触点编号升序分配, 合计恒等于 net_cents。
    对负净额(退款超过成交)同样成立。
    """
    if not weighted_ids:
        return {}
    total_w = sum(w for _, w in weighted_ids)
    shares: list[tuple[int, int, Fraction]] = []  # (id, floor, frac)
    for tid, w in weighted_ids:
        exact = Fraction(net_cents * w, total_w)
        floor_v = exact.numerator // exact.denominator
        shares.append((tid, floor_v, exact - floor_v))
    remainder = net_cents - sum(s[1] for s in shares)
    order = sorted(shares, key=lambda s: (-s[2], s[0]))
    bumped = {s[0] for s in order[:remainder]}
    return {tid: v + (1 if tid in bumped else 0) for tid, v, _ in shares}


def eligible_identities(conv: Conversion, bindings: list[Binding]) -> set[str]:
    """成交时已经建立绑定的匿名身份(不含成交后才绑定的)。"""
    return {
        b.anon_id
        for b in bindings
        if b.user_id == conv.user_id and b.bound_at <= conv.ts
    }


def eligible_touchpoints(
    conv: Conversion,
    touchpoints: list[Touchpoint],
    idents: set[str],
    lookback_days: int,
) -> list[Touchpoint]:
    """成交前(含同一时刻)且在回看窗口内的触点, 按 (时间, 编号) 排序。"""
    window_start = conv.ts - timedelta(days=lookback_days)
    tps = [
        t
        for t in touchpoints
        if t.anon_id in idents and window_start <= t.ts <= conv.ts
    ]
    tps.sort(key=lambda t: (t.ts, t.touchpoint_id))
    return tps


def attribute(
    conv: Conversion,
    touchpoints: list[Touchpoint],
    bindings: list[Binding],
    refund_cents: int,
    model: str,
    lookback_days: int,
) -> tuple[list[Allocation], list[Touchpoint]]:
    """对单笔成交归因。返回 (分摊结果, 窗口内触点)。"""
    if model not in MODELS:
        raise ValueError(f"unknown model: {model}")
    idents = eligible_identities(conv, bindings)
    window = eligible_touchpoints(conv, touchpoints, idents, lookback_days)
    net = 0 if conv.reversed else conv.gross_cents - refund_cents

    if not window:
        return [Allocation(None, UNKNOWN_CHANNEL, Fraction(1), net)], window

    if model == MODEL_FIRST:
        chosen = [window[0]]
    elif model == MODEL_LAST_NON_DIRECT:
        non_direct = [t for t in window if not t.is_direct]
        chosen = [non_direct[-1] if non_direct else window[-1]]
    else:  # linear
        chosen = window

    weights = [(t.touchpoint_id, 1) for t in chosen]
    cents_map = allocate_cents(net, weights)
    n = len(chosen)
    allocs = [
        Allocation(t.touchpoint_id, t.channel, Fraction(1, n), cents_map[t.touchpoint_id])
        for t in chosen
    ]
    return allocs, window
