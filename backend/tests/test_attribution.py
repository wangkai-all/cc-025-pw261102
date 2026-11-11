"""归因规则测试: 用演示数据验证全部业务规则。"""
import pytest

from app import db, seed, service
from app.attribution import (
    MODEL_FIRST,
    MODEL_LAST_NON_DIRECT,
    MODEL_LINEAR,
    UNKNOWN_CHANNEL,
    allocate_cents,
)


@pytest.fixture()
def con():
    c = db.connect()
    seed.seed(c)
    yield c
    c.close()


def by_channel(con, model, lookback=30):
    orders, _, _ = service.compute_all(con, model, lookback)
    return {o["order_id"]: o for o in orders}


# ---- 金额分摊(最大余数法) ----

def test_one_cent_three_way_goes_to_lowest_touchpoint_id():
    # 1 分三方平分: 小数余数相同, 按触点编号升序, 编号 5 拿到这 1 分
    assert allocate_cents(1, [(5, 1), (6, 1), (7, 1)]) == {5: 1, 6: 0, 7: 0}


def test_remainder_by_fraction_then_id():
    # 100 * (1/2, 1/3, 1/6) = 50, 33.33, 16.67 -> 余数 1 分给 0.67
    assert allocate_cents(100, [(1, 1), (2, 2), (3, 3)]) == {1: 17, 2: 33, 3: 50}
    # 合计恒等
    for net in (0, 1, 2, 3, 100, 999, -1, -100):
        r = allocate_cents(net, [(5, 1), (6, 1), (7, 1)])
        assert sum(r.values()) == net


# ---- 窗口与触点资格 ----

def test_cross_day_touchpoint_window(con):
    # O1: 小红书触点(10-30)在 7 天窗口外, 首次触达只能取 SEM(11-06)
    o = by_channel(con, MODEL_FIRST, lookback=7)["O1"]
    assert o["by_channel"] == {"搜索引擎SEM": 10000}
    # 30 天窗口纳入跨日触点, 首次触达变为小红书
    o = by_channel(con, MODEL_FIRST, lookback=30)["O1"]
    assert o["by_channel"] == {"小红书": 10000}


def test_binding_after_conversion_not_used(con):
    # O2a 成交(11-03)时 A2->U2 绑定(11-04)尚未建立 -> 未知来源
    o = by_channel(con, MODEL_FIRST)["O2a"]
    assert o["by_channel"] == {UNKNOWN_CHANNEL: 5000}
    # O2b 成交(11-06)时绑定已建立 -> 可以看到朋友圈广告和直接访问
    o = by_channel(con, MODEL_FIRST)["O2b"]
    assert o["by_channel"] == {"朋友圈广告": 8000}


def test_last_non_direct_prefers_non_direct(con):
    # O2b 窗口内最后触点是直接访问, 末次非直接应取朋友圈广告
    o = by_channel(con, MODEL_LAST_NON_DIRECT)["O2b"]
    assert o["by_channel"] == {"朋友圈广告": 8000}


def test_last_non_direct_falls_back_to_direct(con):
    # O8 只有直接访问 -> 回退到直接访问
    o = by_channel(con, MODEL_LAST_NON_DIRECT)["O8"]
    assert o["by_channel"] == {"直接访问": 2000}


def test_no_touchpoints_unknown(con):
    o = by_channel(con, MODEL_LINEAR)["O7"]
    assert o["by_channel"] == {UNKNOWN_CHANNEL: 4500}


def test_same_timestamp_ordered_by_id(con):
    # O6 两个触点同一时刻, 编号 12(小红书) < 13(SEM)
    o = by_channel(con, MODEL_FIRST)["O6"]
    assert o["by_channel"] == {"小红书": 3000}
    o = by_channel(con, MODEL_LAST_NON_DIRECT)["O6"]
    assert o["by_channel"] == {"搜索引擎SEM": 3000}


# ---- 线性分摊 ----

def test_linear_one_cent(con):
    o = by_channel(con, MODEL_LINEAR)["O3"]
    # 1 分三方平分: 小红书(编号最小)拿 1 分, 其余两个渠道 0 分
    assert o["by_channel"] == {"小红书": 1, "朋友圈广告": 0, "搜索引擎SEM": 0}
    assert sum(o["by_channel"].values()) == 1


def test_linear_partial_refund(con):
    # O4: 10000 - 4000 退款 = 6000, 三个触点平分
    o = by_channel(con, MODEL_LINEAR)["O4"]
    assert o["by_channel"] == {"小红书": 2000, "搜索引擎SEM": 2000, "直接访问": 2000}
    # 首次触达则净额全部给小红书
    o = by_channel(con, MODEL_FIRST)["O4"]
    assert o["by_channel"] == {"小红书": 6000}


# ---- 撤销 / 复用 / 幂等 ----

def test_reversed_conversion_zero(con):
    for model in (MODEL_FIRST, MODEL_LAST_NON_DIRECT, MODEL_LINEAR):
        o = by_channel(con, model)["O5"]
        assert o["net_cents"] == 0
        assert o["by_channel"] == {"朋友圈广告": 0}


def test_touchpoints_reused_across_conversions(con):
    # A2 的朋友圈触点同时出现在 O2b 的窗口里; 同一触点可被多笔成交复用
    detail = service.conversion_detail(con, "O2b", MODEL_LINEAR, 30)
    ids = [t["touchpoint_id"] for t in detail["touchpoints"] if t["status"] == "credited"]
    assert ids == [3, 4]


def test_duplicate_import_idempotent(con):
    before, _, total_before = service.compute_all(con, MODEL_LINEAR, 30)
    # 再导入一遍同样的成交和触点
    db.import_conversions(con, seed.CONVERSIONS)
    db.import_touchpoints(con, seed.TOUCHPOINTS)
    db.import_refunds(con, seed.REFUNDS)
    after, _, total_after = service.compute_all(con, MODEL_LINEAR, 30)
    assert total_after == total_before
    assert [o["order_id"] for o in after] == [o["order_id"] for o in before]
    assert db.counts(con)["conversions"] == len(seed.CONVERSIONS)


def test_channel_totals_match_net(con):
    for model in (MODEL_FIRST, MODEL_LAST_NON_DIRECT, MODEL_LINEAR):
        for lookback in (1, 7, 30):
            orders, summary, total = service.compute_all(con, model, lookback)
            assert sum(s["net_cents"] for s in summary) == total
            assert sum(sum(o["by_channel"].values()) for o in orders) == total
