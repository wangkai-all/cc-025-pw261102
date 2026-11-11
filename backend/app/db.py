"""DuckDB 存储层: 建表、幂等导入、读取。"""
from __future__ import annotations

from datetime import datetime

import duckdb

from .attribution import Binding, Conversion, Touchpoint

SCHEMA = """
CREATE TABLE IF NOT EXISTS touchpoints (
    touchpoint_id INTEGER PRIMARY KEY,
    anon_id VARCHAR NOT NULL,
    channel VARCHAR NOT NULL,
    is_direct BOOLEAN NOT NULL,
    ts TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS identity_bindings (
    anon_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    bound_at TIMESTAMP NOT NULL,
    PRIMARY KEY (anon_id, user_id)
);
CREATE TABLE IF NOT EXISTS conversions (
    order_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    gross_cents BIGINT NOT NULL,
    ts TIMESTAMP NOT NULL,
    reversed BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS refunds (
    refund_id VARCHAR PRIMARY KEY,
    order_id VARCHAR NOT NULL,
    amount_cents BIGINT NOT NULL,
    ts TIMESTAMP NOT NULL
);
"""


def connect(path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(path)
    con.execute(SCHEMA)
    return con


def reset(con: duckdb.DuckDBPyConnection) -> None:
    for table in ("touchpoints", "identity_bindings", "conversions", "refunds"):
        con.execute(f"DELETE FROM {table}")


# ---- 导入(全部按主键幂等, 重复导入不累加) ----

def import_touchpoints(con, rows: list[dict]) -> int:
    con.executemany(
        "INSERT OR REPLACE INTO touchpoints VALUES (?, ?, ?, ?, ?)",
        [
            (r["touchpoint_id"], r["anon_id"], r["channel"], bool(r["is_direct"]), _ts(r["ts"]))
            for r in rows
        ],
    )
    return len(rows)


def import_bindings(con, rows: list[dict]) -> int:
    con.executemany(
        "INSERT OR REPLACE INTO identity_bindings VALUES (?, ?, ?)",
        [(r["anon_id"], r["user_id"], _ts(r["bound_at"])) for r in rows],
    )
    return len(rows)


def import_conversions(con, rows: list[dict]) -> int:
    con.executemany(
        "INSERT OR REPLACE INTO conversions VALUES (?, ?, ?, ?, ?)",
        [
            (r["order_id"], r["user_id"], int(r["gross_cents"]), _ts(r["ts"]), bool(r.get("reversed", False)))
            for r in rows
        ],
    )
    return len(rows)


def import_refunds(con, rows: list[dict]) -> int:
    con.executemany(
        "INSERT OR REPLACE INTO refunds VALUES (?, ?, ?, ?)",
        [(r["refund_id"], r["order_id"], int(r["amount_cents"]), _ts(r["ts"])) for r in rows],
    )
    return len(rows)


def _ts(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


# ---- 读取 ----

def load_touchpoints(con) -> list[Touchpoint]:
    rows = con.execute(
        "SELECT touchpoint_id, anon_id, channel, is_direct, ts FROM touchpoints"
    ).fetchall()
    return [Touchpoint(int(r[0]), r[1], r[2], bool(r[3]), r[4]) for r in rows]


def load_bindings(con) -> list[Binding]:
    rows = con.execute("SELECT anon_id, user_id, bound_at FROM identity_bindings").fetchall()
    return [Binding(r[0], r[1], r[2]) for r in rows]


def load_conversions(con) -> list[Conversion]:
    rows = con.execute(
        "SELECT order_id, user_id, gross_cents, ts, reversed FROM conversions ORDER BY ts, order_id"
    ).fetchall()
    return [Conversion(r[0], r[1], int(r[2]), r[3], bool(r[4])) for r in rows]


def load_refund_map(con) -> dict[str, int]:
    rows = con.execute(
        "SELECT order_id, COALESCE(SUM(amount_cents), 0) FROM refunds GROUP BY order_id"
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def load_refunds_for(con, order_id: str) -> list[dict]:
    rows = con.execute(
        "SELECT refund_id, amount_cents, ts FROM refunds WHERE order_id = ? ORDER BY ts, refund_id",
        [order_id],
    ).fetchall()
    return [{"refund_id": r[0], "amount_cents": int(r[1]), "ts": r[2].isoformat()} for r in rows]


def counts(con) -> dict[str, int]:
    out = {}
    for table in ("touchpoints", "identity_bindings", "conversions", "refunds"):
        out[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return out
