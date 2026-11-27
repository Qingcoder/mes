"""数据模型 · 戴盟 MES 生产管理平台
用 SQLAlchemy ORM 抽象，SQLite 起步、将来迁 PostgreSQL 只需改连接串。
SN 状态流转收敛在 service 层，页面只调 API。
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, JSON,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password = Column(String(128), nullable=False)  # V1 演示用明文，V1.1 改哈希
    name = Column(String(64))
    role = Column(String(32), default="")
    avatar = Column(String(8), default="")  # V1.1 头像字符/emoji，1-2 字符，后端校验


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)


class WorkOrder(Base):
    __tablename__ = "wos"
    id = Column(Integer, primary_key=True, index=True)
    wo_no = Column(String(64), unique=True, nullable=False, index=True)
    product = Column(String(128), nullable=False)
    batch = Column(String(64))
    plan_qty = Column(Integer, default=0)
    location = Column(String(64), default="戴盟公司")
    stations = Column(JSON, default=list)     # 每工单可配的站点序列 ["压力测试",...]
    pack_qty = Column(Integer, default=1)     # 自定义配比 N 台/箱
    status = Column(String(32), default="draft")  # draft/released/running/finished/closed
    rev = Column(Integer, default=0, nullable=False)  # 乐观锁版本号
    created_at = Column(DateTime, default=datetime.utcnow)

    sns = relationship("Unit", back_populates="wo", cascade="all, delete-orphan")


class Unit(Base):
    """一台 SN 的当前状态。状态机：pending→passed/failed→rework→station_done→packed"""
    __tablename__ = "units"
    id = Column(Integer, primary_key=True, index=True)
    sn = Column(String(64), unique=True, nullable=False, index=True)
    wo_id = Column(Integer, ForeignKey("wos.id"), nullable=False)
    current_station = Column(String(64))
    state = Column(String(32), default="pending", index=True)
    fail_code = Column(String(64))
    box_no = Column(String(64))
    origin_sn = Column(String(64), index=True)     # 首次建档的原始 SN
    replaced_count = Column(Integer, default=0)    # 被替换次数
    created_at = Column(DateTime, default=datetime.utcnow)

    wo = relationship("WorkOrder", back_populates="sns")
    records = relationship("StationRecord", back_populates="unit", cascade="all, delete-orphan")
    replacements = relationship("SnReplacement", back_populates="unit", cascade="all, delete-orphan")


class SnReplacement(Base):
    """SN 替换记录：一次替换 = 旧 SN 换成新 SN，可连续多次形成替换链。"""
    __tablename__ = "sn_replacements"
    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    wo_id = Column(Integer, ForeignKey("wos.id"), nullable=False, index=True)
    old_sn = Column(String(64), nullable=False, index=True)
    new_sn = Column(String(64), nullable=False, index=True)
    station = Column(String(64))
    reason = Column(String(256))
    operator = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    unit = relationship("Unit", back_populates="replacements")


class StationRecord(Base):
    """过站记录：引用式关联 SN，不把字段塞进 units 表（借鉴 KTG source_doc_id）"""
    __tablename__ = "station_records"
    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    station = Column(String(64), nullable=False)
    result = Column(String(16), nullable=False)   # pass/fail/rework
    fail_code = Column(String(64))
    source_type = Column(String(32), default="station")  # 预留统一待检队列
    operator = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    unit = relationship("Unit", back_populates="records")


class Box(Base):
    __tablename__ = "boxes"
    id = Column(Integer, primary_key=True, index=True)
    box_no = Column(String(64), unique=True, nullable=False, index=True)
    wo_id = Column(Integer, ForeignKey("wos.id"), nullable=False)
    qty = Column(Integer, default=0)
    status = Column(String(32), default="open")  # open/closed
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)


# ---- V1.1 角色与权限（RBAC）----
class Role(Base):
    """角色：单管理员模式仅保留 admin。code 唯一，供账号 role 字段引用。"""
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(256))
    builtin = Column(Boolean, default=False)  # 内置角色不可删除


class Permission(Base):
    """权限点：如 wo:create / station:pass / system:role:manage。"""
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)
    module = Column(String(32), nullable=False, index=True)  # 菜单/模块分组


class RolePermission(Base):
    """角色-权限关联（多对多，显式表便于增删）。"""
    __tablename__ = "role_permissions"
    id = Column(Integer, primary_key=True, index=True)
    role_code = Column(String(32), ForeignKey("roles.code"), nullable=False, index=True)
    perm_code = Column(String(64), ForeignKey("permissions.code"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("role_code", "perm_code"),)


# ---- V1.2 MES 扩展：不良处置闭环 / 审计日志（ISA-95 质量域 + 合规追溯）----
class Ncr(Base):
    """NCR 不合格品处置单：failed SN → 评审 → 返修/报废/让步 → 闭环。"""
    __tablename__ = "ncrs"
    id = Column(Integer, primary_key=True, index=True)
    ncr_no = Column(String(64), unique=True, nullable=False, index=True)
    sn = Column(String(64), nullable=False, index=True)
    wo_id = Column(Integer, ForeignKey("wos.id"), nullable=True, index=True)
    station = Column(String(64))
    fail_code = Column(String(64))
    status = Column(String(32), default="open", index=True)  # open/reviewing/rework/scrap/concession/closed
    disposition = Column(String(32))   # rework/scrap/concession
    note = Column(String(256))
    operator = Column(String(64))      # 登记人
    reviewer = Column(String(64))      # 评审人
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)


class AuditLog(Base):
    """操作审计：谁/何时/对什么/做了什么（合规追溯基础）。"""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    username = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)   # wo.create / station.pass / pack.close ...
    target = Column(String(128))
    detail = Column(String(512))

