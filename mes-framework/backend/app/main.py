"""MES 基础功能框架 · 应用入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8010
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, engine, SessionLocal
from . import models  # noqa: F401  确保模型注册到 metadata
from .seed import seed
from .routers import master, orders, equipment, records, dashboard

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MES 基础功能框架", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(master.router)
app.include_router(orders.router)
app.include_router(equipment.router)
app.include_router(records.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def on_startup():
    seed(SessionLocal())


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
