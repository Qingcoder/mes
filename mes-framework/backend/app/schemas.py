"""Pydantic 请求/响应模型。"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductIn(BaseModel):
    code: str
    name: str


class ProductOut(ORMModel):
    id: int
    code: str
    name: str


class RouteIn(BaseModel):
    code: str
    name: str
    product_id: int
    version: str = "1.0"
    operations: List[Dict[str, Any]] = []


class RouteOut(ORMModel):
    id: int
    code: str
    name: str
    product_id: int
    version: str
    operations: List[Dict[str, Any]]


class EquipmentIn(BaseModel):
    code: str
    name: str
    status: str = "idle"


class EquipmentStatusIn(BaseModel):
    status: str
    reason: str = ""


class EquipmentOut(ORMModel):
    id: int
    code: str
    name: str
    status: str
    current_order_id: Optional[int] = None
    current_operation_id: Optional[int] = None
    updated_at: datetime


class EquipmentEventOut(ORMModel):
    id: int
    equipment_id: int
    from_status: str
    to_status: str
    reason: str
    at: datetime


class OrderIn(BaseModel):
    product_id: int
    route_id: int
    plan_qty: int
    order_no: Optional[str] = None


class OperationOut(ORMModel):
    id: int
    work_order_id: int
    seq: int
    name: str
    standard_minutes: int
    status: str
    plan_qty: int
    good_qty: int
    bad_qty: int
    equipment_id: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class RecordIn(BaseModel):
    good_qty: int
    bad_qty: int = 0
    operator: str = ""
    equipment_id: Optional[int] = None
    note: str = ""


class RecordOut(ORMModel):
    id: int
    work_order_id: int
    operation_id: int
    equipment_id: Optional[int]
    operator: str
    good_qty: int
    bad_qty: int
    note: str
    recorded_at: datetime


class OrderOut(ORMModel):
    id: int
    order_no: str
    product_id: int
    route_id: int
    plan_qty: int
    status: str
    current_seq: int
    created_at: datetime
    released_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    operations: List[OperationOut] = []
    records: List[RecordOut] = []
