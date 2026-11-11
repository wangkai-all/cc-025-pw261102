"""FastAPI 入口: 数据导入、渠道汇总、成交路径、口径对比。"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db, seed, service
from .attribution import MODEL_FIRST, MODEL_LABELS, MODEL_LAST_NON_DIRECT, MODEL_LINEAR, MODELS

ModelKey = Literal["first_touch", "last_non_direct", "linear"]

app = FastAPI(title="多触点归因")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("ATTRIBUTION_DB", ":memory:")
con = db.connect(DB_PATH)


@app.get("/api/meta")
def meta():
    return {
        "models": [{"key": m, "label": MODEL_LABELS[m]} for m in MODELS],
        "counts": db.counts(con),
    }


@app.post("/api/import/{entity}")
def import_entity(entity: str, rows: list[dict]):
    importers = {
        "touchpoints": db.import_touchpoints,
        "identity_bindings": db.import_bindings,
        "conversions": db.import_conversions,
        "refunds": db.import_refunds,
    }
    if entity not in importers:
        raise HTTPException(404, f"未知数据类型: {entity}")
    try:
        n = importers[entity](con, rows)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(422, f"数据格式错误: {e}")
    return {"imported": n, "counts": db.counts(con)}


@app.post("/api/seed")
def load_seed():
    return {"counts": seed.seed(con)}


@app.post("/api/reset")
def reset():
    db.reset(con)
    return {"counts": db.counts(con)}


@app.get("/api/summary")
def summary(model: ModelKey = MODEL_LAST_NON_DIRECT, lookback_days: int = Query(30, ge=1, le=365)):
    _, channel_summary, total_net = service.compute_all(con, model, lookback_days)
    return {"model": model, "lookback_days": lookback_days, "total_net_cents": total_net, "channels": channel_summary}


@app.get("/api/conversions")
def conversions(model: ModelKey = MODEL_LAST_NON_DIRECT, lookback_days: int = Query(30, ge=1, le=365)):
    per_order, _, total_net = service.compute_all(con, model, lookback_days)
    return {"model": model, "lookback_days": lookback_days, "total_net_cents": total_net, "orders": per_order}


@app.get("/api/conversions/{order_id}")
def conversion_detail(order_id: str, model: ModelKey = MODEL_LAST_NON_DIRECT, lookback_days: int = Query(30, ge=1, le=365)):
    detail = service.conversion_detail(con, order_id, model, lookback_days)
    if detail is None:
        raise HTTPException(404, f"成交不存在: {order_id}")
    return detail


@app.get("/api/compare")
def compare(lookback_days: int = Query(30, ge=1, le=365)):
    return service.compare(con, lookback_days)


# 生产模式: 服务前端构建产物(存在时)
_static = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")
