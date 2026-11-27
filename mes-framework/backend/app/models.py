"""MES 核心数据模型。

设计参考：六大主数据（产品/工艺路线/工序/BOM/设备/人员）与五大业务流
（工单执行、物料流转、质量管控、设备运维、异常）；本框架先落地与
「生产订单 → 工序 → 报工 → 设备 → 看板」闭环直接相关的实体。
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Route(Base):
    """工艺路线模板：operations 为工序定义列表，工单创建时展开为工单工序实例。"""
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    version = Column(String(32), default="1.0")
    operations = Column(JSON, default=list)  # [{name, sequence, standard_minutes, equipment_code}]
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), default="idle", index=True)  # idle/running/down/maintenance
    current_order_id = Column(Integer, nullable=True)
    current_operation_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkOrder(Base):
    """生产订单：引用产品与工艺路线版本，持有工序实例与执行状态。"""
    __tablename__ = "work_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(64), unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    plan_qty = Column(Integer, nullable=False)
    status = Column(String(32), default="draft", index=True)  # draft/released/in_progress/completed/closed
    current_seq = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    released_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    product = relationship("Product")
    route = relationship("Route")
    operations = relationship("WorkOrderOperation", back_populates="order", cascade="all, delete-orphan", order_by="WorkOrderOperation.seq")
    records = relationship("ProductionRecord", back_populates="order", cascade="all, delete-orphan")


class WorkOrderOperation(Base):
    """工单工序：工艺路线工序的执行实例，报工事件累加到此对象。"""
    __tablename__ = "work_order_operations"
    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    name = Column(String(128), nullable=False)
    standard_minutes = Column(Integer, default=0)
    status = Column(String(32), default="pending", index=True)  # pending/in_progress/done
    plan_qty = Column(Integer, nullable=False)
    good_qty = Column(Integer, default=0)
    bad_qty = Column(Integer, default=0)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    order = relationship("WorkOrder", back_populates="operations")
    equipment = relationship("Equipment")
    records = relationship("ProductionRecord", back_populates="operation", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("work_order_id", "seq"),)


class ProductionRecord(Base):
    """报工/采集记录：原始事实数据，保留快照字段用于追溯。"""
    __tablename__ = "production_records"
    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    operation_id = Column(Integer, ForeignKey("work_order_operations.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True, index=True)
    operator = Column(String(64), default="")
    good_qty = Column(Integer, default=0)
    bad_qty = Column(Integer, default=0)
    note = Column(Text, default="")
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    order = relationship("WorkOrder", back_populates="records")
    operation = relationship("WorkOrderOperation", back_populates="records")
    equipment = relationship("Equipment")


class EquipmentEvent(Base):
    """设备状态变更日志：为设备监控与 OEE 统计提供历史依据。"""
    __tablename__ = "equipment_events"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    from_status = Column(String(32), default="")
    to_status = Column(String(32), nullable=False)
    reason = Column(String(256), default="")
    at = Column(DateTime, default=datetime.utcnow, index=True)

    equipment = relationship("Equipment")
