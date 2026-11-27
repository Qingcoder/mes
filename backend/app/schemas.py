"""Pydantic 请求/响应模型"""
from typing import Any, Optional, List
from datetime import datetime
from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    ok: bool
    token: Optional[str] = None
    username: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    msg: Optional[str] = None


class WOIn(BaseModel):
    wo_no: str = ""
    product: str
    batch: Optional[str] = None
    plan_qty: int = 0
    location: Optional[str] = "戴盟公司"
    stations: List[str] = []
    pack_qty: int = 1
    relatedEquipment: List[Any] = []
    relatedPersons: List[Any] = []
    rev: Optional[int] = None   # 更新时带版本号


class SNImportIn(BaseModel):
    wo_id: int
    sns: List[str]


class StationIn(BaseModel):
    sn: str
    station: str
    result: str          # pass / fail
    fail_code: Optional[str] = None
    operator: Optional[str] = None
    rev: Optional[int] = None


class SnReplaceIn(BaseModel):
    sn: str
    new_sn: str
    station: str = ""
    reason: str = ""
    operator: Optional[str] = None


class PackIn(BaseModel):
    box_no: str
    sns: List[str]
    operator: Optional[str] = None


class WOLine(BaseModel):
    id: int
    wo_no: str
    product: str
    batch: Optional[str] = None
    plan_qty: int
    location: Optional[str] = None
    stations: List[str] = []
    pack_qty: int = 1
    relatedProducts: List[dict] = []
    relatedEquipment: List[dict] = []
    relatedPersons: List[dict] = []
    relatedStations: List[dict] = []
    status: str
    rev: int

    class Config:
        from_attributes = True


class UnitLine(BaseModel):
    id: int
    sn: str
    wo_no: Optional[str] = None
    current_station: Optional[str] = None
    state: str
    fail_code: Optional[str] = None
    box_no: Optional[str] = None

    class Config:
        from_attributes = True


class RecordLine(BaseModel):
    id: int
    sn: Optional[str] = None
    station: str
    result: str
    fail_code: Optional[str] = None
    operator: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BoxLine(BaseModel):
    id: int
    box_no: str
    wo_no: Optional[str] = None
    qty: int
    status: str
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- V1.1 角色与权限（RBAC）----
class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    builtin: bool = False

    class Config:
        from_attributes = True


class PermissionOut(BaseModel):
    id: int
    code: str
    name: str
    module: str

    class Config:
        from_attributes = True


class RoleIn(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class RolePermIn(BaseModel):
    perms: List[str]   # 权限 code 列表，全量覆盖该角色已有权限


class UserOut(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    role: Optional[str] = None
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class UserIn(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    role: str


class ProfileIn(BaseModel):
    name: str
    avatar: str = ""


# ---- V1.2 MES 扩展 ----
class NcrIn(BaseModel):
    sn: str
    note: Optional[str] = None


class NcrDisposeIn(BaseModel):
    disposition: str   # rework / scrap / concession
    note: Optional[str] = None


class NcrOut(BaseModel):
    id: int
    ncr_no: str
    sn: str
    wo_id: Optional[int] = None
    station: Optional[str] = None
    fail_code: Optional[str] = None
    status: str
    disposition: Optional[str] = None
    note: Optional[str] = None
    operator: Optional[str] = None
    reviewer: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditOut(BaseModel):
    id: int
    ts: datetime
    username: str
    action: str
    target: Optional[str] = None
    detail: Optional[str] = None

    class Config:
        from_attributes = True
