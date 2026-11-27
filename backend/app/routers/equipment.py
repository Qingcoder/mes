"""设备管理接口。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, deps, equipment_store, models, permission_guard, process_design_store, product_profiles_store, relation_store

router = APIRouter(
    prefix="/api/equipment", tags=["设备管理"],
    dependencies=[Depends(auth.current_account)],
)


get_db = deps.get_db


def _require_manage(db: Session, account: models.Account) -> str:
    codes = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if account.role != "admin" and "machine:manage" not in codes:
        raise HTTPException(403, "当前账号无设备管理权限")
    return account.username


def _handle(exc: Exception):
    raise HTTPException(400, str(exc))


@router.get("/summary")
def summary(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    counts = equipment_store.status_counts()
    return {
        "total": sum(counts.values()),
        "counts": [
            {"value": key, "label": equipment_store.status_label(key), "count": value}
            for key, value in counts.items()
        ],
    }


@router.get("/options")
def options(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    products = [
        {"code": str(row.get("code") or "").upper(), "name": str(row.get("name") or "")}
        for row in product_profiles_store.list_profiles() if row.get("code")
    ]
    stations = [
        {"code": str(row.get("code") or "").upper(), "name": str(row.get("name") or "")}
        for row in process_design_store.load_config().get("stations", []) if row.get("code")
    ]
    persons = []
    for row in db.query(models.Account).order_by(models.Account.name.asc()).all():
        persons.append({"username": row.username, "name": row.name or row.username})
    return {"products": products, "stations": stations, "persons": persons}


@router.get("")
def devices(
    q: str = "", status: str = "", category: str = "",
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    return [relation_store.enrich_device(row, db) for row in equipment_store.list_devices(q, status, category)]


@router.get("/{code}")
def detail(code: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    device = equipment_store.find_device(code)
    if not device:
        raise HTTPException(404, "设备不存在")
    return relation_store.enrich_device(device, db)


@router.post("")
def create_device(
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        device = equipment_store.create_device(payload, actor)
        relation_store.apply_full_selection("equipment", device["code"], relation_store.device_relations(device, db, payload), db)
        relation_store.sync_all(db)
        device = relation_store.enrich_device(device, db)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "equipment.create", device["code"], device["name"], commit=True)
    return device


@router.post("/import")
def import_devices(
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        result = equipment_store.import_devices(payload.get("rows") or [], actor)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(
        db, actor, "equipment.import", "equipment",
        f"created={result['createdCount']}; skipped={result['skippedCount']}", commit=True,
    )
    return result


@router.put("/{code}")
def update_device(
    code: str,
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        device = equipment_store.update_device(code, payload, actor)
        relation_store.apply_full_selection("equipment", code, relation_store.device_relations(device, db), db)
        relation_store.sync_all(db)
        device = relation_store.enrich_device(device, db)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "equipment.update", code, device["name"], commit=True)
    return device


@router.delete("/{code}")
def delete_device(
    code: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        removed = equipment_store.delete_device(code)
        relation_store.remove_source("equipment", code)
        relation_store.sync_all(db)
    except ValueError as exc:
        _handle(exc)
    if not removed:
        raise HTTPException(404, "设备不存在")
    permission_guard.write_audit(db, actor, "equipment.delete", code, "", commit=True)
    return {"ok": True}


@router.post("/{code}/maintenance")
def add_maintenance(
    code: str,
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        record = equipment_store.add_maintenance(code, payload, actor)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "equipment.maintenance.create", code, record["type"], commit=True)
    return record


@router.put("/{code}/maintenance/{record_id}")
def update_maintenance(
    code: str,
    record_id: str,
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        record = equipment_store.update_maintenance(code, record_id, payload, actor)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "equipment.maintenance.update", code, record_id, commit=True)
    return record


@router.delete("/{code}/maintenance/{record_id}")
def delete_maintenance(
    code: str,
    record_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        equipment_store.delete_maintenance(code, record_id, actor)
    except ValueError as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "equipment.maintenance.delete", code, record_id, commit=True)
    return {"ok": True}
