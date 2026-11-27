"""环境配置接口：全局资料库与模块基础信息总览。"""
import json
import os
from typing import Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import (
    auth, custom_site_store, deps, domain_config_store, environment_store, equipment_store,
    function_tree_store, models, module_skeleton_store,
    permission_guard, personnel_store, process_design_store,
    product_profiles_store,
)

router = APIRouter(
    prefix="/api/environment", tags=["环境配置"],
    dependencies=[Depends(auth.current_account)],
)


get_db = deps.get_db


def _require_manage(db: Session, account: models.Account) -> str:
    codes = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if account.role != "admin" and "environment:manage" not in codes:
        raise HTTPException(403, "当前账号无环境配置权限")
    return account.username


def _readonly_mode() -> bool:
    """共享资料库当前只读：写入能力迁往新模块，这里留开关以便后续放开。

    默认只读；把环境变量 MES_ENVIRONMENT_READONLY 设为 0/false/off 可恢复写入。
    """
    value = os.getenv("MES_ENVIRONMENT_READONLY", "1").strip().lower()
    return value not in ("0", "false", "off", "no")


def _readonly_guard() -> None:
    """只读闸门（路由依赖）。

    必须挂在路由依赖上而不是函数体里：FastAPI 会先校验请求体再进函数体，
    放在函数体里等于先把整个上传文件收完再拒绝。
    """
    if _readonly_mode():
        raise HTTPException(403, "共享资料库当前为只读模式，写入入口迁移中，暂不可上传/编辑/删除")


def _count(fn, default=0):
    try:
        value = fn()
        return len(value) if isinstance(value, (list, tuple, dict)) else default
    except Exception:
        return default


def _parse_relation_items(raw: str, field: str):
    try:
        value = json.loads(raw or "[]")
    except Exception:
        raise HTTPException(400, field + " 格式不正确")
    if not isinstance(value, list):
        raise HTTPException(400, field + " 必须是数组")
    return value


def _station_options() -> List[Dict[str, str]]:
    """站点（工艺/工站）选项，字段名与 relation_store 的 stations 保持一致。"""
    return [
        {"code": str(row.get("code") or "").upper(), "name": str(row.get("name") or "")}
        for row in process_design_store.load_config().get("stations", []) if row.get("code")
    ]


@router.get("/options")
def resource_options(db: Session = Depends(get_db), account: models.Account = Depends(auth.current_account)):
    _require_manage(db, account)
    return {
        "persons": [
            {"code": row.username, "name": row.name or row.username}
            for row in db.query(models.Account).order_by(models.Account.name.asc()).all()
        ],
        "products": [
            {"code": str(row.get("code") or "").upper(), "name": str(row.get("name") or "")}
            for row in product_profiles_store.list_profiles() if row.get("code")
        ],
        "equipment": [
            {"code": str(row.get("code") or "").upper(), "name": str(row.get("name") or "")}
            for row in equipment_store.list_devices() if row.get("code")
        ],
        "processes": _station_options(),
        "stations": _station_options(),
    }


@router.get("/resources")
def resources(
    module: str = "", category: str = "", q: str = "",
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    return environment_store.list_resources(module, category, q)


@router.post("/resources", dependencies=[Depends(_readonly_guard)])
async def upload_resource(
    title: str = Form(...),
    module: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    relatedPersons: str = Form("[]"),
    relatedProducts: str = Form("[]"),
    relatedEquipment: str = Form("[]"),
    relatedStations: str = Form("[]"),
    relatedProcesses: str = Form("[]"),
    file: UploadFile = File(...),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    content = await file.read(environment_store.MAX_FILE_SIZE + 1)
    try:
        meta = environment_store.resource_meta({
            "title": title, "module": module, "category": category,
            "description": description, "fileName": file.filename or "",
            "contentType": file.content_type or "", "uploadedBy": actor,
            "relatedPersons": _parse_relation_items(relatedPersons, "关联人员"),
            "relatedProducts": _parse_relation_items(relatedProducts, "关联产品"),
            "relatedEquipment": _parse_relation_items(relatedEquipment, "关联设备"),
            "relatedStations": _parse_relation_items(relatedStations, "关联工艺"),
            "relatedProcesses": _parse_relation_items(relatedProcesses, "关联工艺"),
        }, len(content))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    environment_store.create_resource(meta, content)
    permission_guard.write_audit(db, actor, "environment.resource.upload", module, f"{meta['id']} {meta['fileName']}", commit=True)
    return meta


@router.put("/resources/{resource_id}", dependencies=[Depends(_readonly_guard)])
def update_resource(
    resource_id: str,
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    payload = dict(payload or {})
    payload["updatedBy"] = actor
    try:
        row = environment_store.update_resource(resource_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    permission_guard.write_audit(db, actor, "environment.resource.update", str(row.get("module", "")), resource_id, commit=True)
    return row


@router.get("/resources/{resource_id}/download")
def download_resource(
    resource_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    row = environment_store.find_resource(resource_id)
    if not row:
        raise HTTPException(404, "资料不存在")
    try:
        path = environment_store.resource_path(row)
    except FileNotFoundError:
        raise HTTPException(404, "资料文件不存在")
    return FileResponse(path, filename=row.get("fileName") or resource_id, media_type=row.get("contentType"))


@router.delete("/resources/{resource_id}", dependencies=[Depends(_readonly_guard)])
def delete_resource(
    resource_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        row = environment_store.delete_resource(resource_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    permission_guard.write_audit(db, actor, "environment.resource.delete", str(row.get("module", "")), resource_id, commit=True)
    return {"ok": True}


def _module(key, label, route, permission, counts):
    return {"key": key, "label": label, "route": route, "permission": permission, "counts": counts}


@router.get("/overview")
def overview(db: Session = Depends(get_db), account: models.Account = Depends(auth.current_account)):
    _require_manage(db, account)
    process = process_design_store.load_config()
    domain = domain_config_store.load_config()
    custom = custom_site_store.load_config()
    tree = function_tree_store.load_tree()
    products = product_profiles_store.list_profiles()
    resources = environment_store.list_resources()

    modules = [
        _module("dashboard", "看板", "/dashboard", "dashboard:view", [
            {"label": "工单", "value": db.query(models.WorkOrder).count()},
            {"label": "SN", "value": db.query(models.Unit).count()},
            {"label": "箱号", "value": db.query(models.Box).count()},
            {"label": "过站记录", "value": db.query(models.StationRecord).count()},
        ]),
        _module("person", "人员管理", "/person", "person:manage", [
            {"label": "账号", "value": db.query(models.Account).count()},
            {"label": "人员档案", "value": _count(personnel_store.list_persons)},
            {"label": "角色", "value": db.query(models.Role).count()},
        ]),
        _module("machine", "设备管理", "/machine", "machine:manage", [
            {"label": "设备台账", "value": len(equipment_store.list_devices())},
            {"label": "运行中", "value": equipment_store.status_counts().get("running", 0)},
            {"label": "维修中", "value": equipment_store.status_counts().get("maintenance", 0)},
        ]),
        _module("material", "物料管理", "/material", "material:manage", [
            {"label": "产品", "value": db.query(models.Product).count()},
            {"label": "产品档案", "value": len(products)},
            {"label": "SN", "value": sum(len(s.get("sns") or []) for p in products for s in p.get("sides", []))},
        ]),
        _module("method", "工艺管理", "/method", "method:manage", [
            {"label": "站点", "value": len(process.get("stations", []))},
            {"label": "库分组", "value": len(process.get("library", []))},
            {"label": "库项", "value": sum(len(g.get("items") or []) for g in process.get("library", []))},
            {"label": "站点类型", "value": len(process.get("options", {}).get("stationTypes", []))},
        ]),
        _module("environment", "共享资料库", "/environment", "environment:manage", [
            {"label": "资料", "value": len(resources)},
            {"label": "自定义站点", "value": len(custom.get("sites", []))},
            {"label": "站点分组", "value": len(custom.get("groups", []))},
            {"label": "功能节点", "value": _count(lambda: tree.get("functions", []))},
            {"label": "领域配置", "value": len(domain.get("domains", []))},
        ]),
        _module("wo", "工单管理", "/wo", "wo:view", [
            {"label": "工单", "value": db.query(models.WorkOrder).count()},
            {"label": "SN", "value": db.query(models.Unit).count()},
        ]),
        _module("station", "站点作业", "/station", "station:op", [
            {"label": "站点", "value": len(process.get("stations", []))},
            {"label": "过站记录", "value": db.query(models.StationRecord).count()},
        ]),
        _module("pack", "包装管理", "/pack", "pack:op", [
            {"label": "箱号", "value": db.query(models.Box).count()},
            {"label": "已装箱 SN", "value": db.query(models.Unit).filter(models.Unit.box_no != "").count()},
        ]),
        _module("query", "数据查询", "/query", "query:view", [
            {"label": "SN", "value": db.query(models.Unit).count()},
            {"label": "过站记录", "value": db.query(models.StationRecord).count()},
            {"label": "不良品", "value": db.query(models.Unit).filter(models.Unit.state == "failed").count()},
        ]),
        _module("quality", "质量控制", "/query", "query:view", [
            {"label": "NCR", "value": db.query(models.Ncr).count()},
            {"label": "不良品", "value": db.query(models.Unit).filter(models.Unit.state == "failed").count()},
        ]),
        _module("account", "账户权限", "/roles", "system:role:manage", [
            {"label": "账号", "value": db.query(models.Account).count()},
            {"label": "角色", "value": db.query(models.Role).count()},
            {"label": "权限点", "value": db.query(models.Permission).count()},
            {"label": "审计", "value": db.query(models.AuditLog).count()},
        ]),
    ]
    return {"generatedAt": environment_store._now(), "modules": modules}
