"""FastAPI 请求作用域依赖。

按 FastAPI + SQLAlchemy 官方规范：
- 所有路由与子依赖必须使用同一个 get_db callable；
- yield 依赖必须使用 try/finally 保证 Session.close()；
- 同一请求内的查询、修改与提交共享同一个 Session。
"""
from sqlalchemy.orm import Session


def get_db():
    from .main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
