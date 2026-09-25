"""雾化管路配平 Web 应用：业务 API + 静态页面 + 健康检查。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .models import BalanceRequest
from .solver import solve
app = FastAPI(title="纸本修复雾化管路配平", version="1.0.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@app.post("/api/balance")
def balance(req: BalanceRequest) -> dict:
    result = solve(req)
    return result.model_dump()


# 根路由兜底：静态页面（/、/app.js 等）。需在最后注册。
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="root")
