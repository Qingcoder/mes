"""SN 库接口。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from .. import auth, deps, models, permission_guard, sn_library_store

router = APIRouter(
    prefix="/api/sn-library", tags=["SN库"],
    dependencies=[Depends(auth.current_account)],
)

get_db = deps.get_db


class SnLibraryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sn: str = ""
    product: str = ""
    remark: str = ""


def _require_view(db: Session, account: models.Account) -> str:
    codes = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if account.role != "admin" and not ({"wo:view", "sn:import"} & codes):
        raise HTTPException(403, "当前账号无 SN 库查看权限")
    return account.username


def _require_manage(db: Session, account: models.Account) -> str:
    codes = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if account.role != "admin" and not ({"wo:create", "material:manage", "sn:import"} & codes):
        raise HTTPException(403, "当前账号无 SN 库维护权限")
    return account.username


@router.get("/summary")
def summary(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_view(db, account)
    return sn_library_store.summary()


@router.get("")
def records(keyword: str = "", product: str = "", account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_view(db, account)
    return sn_library_store.list_records(keyword, product)


@router.get("/{record_id}")
def detail(record_id: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_view(db, account)
    row = sn_library_store.find_record(record_id)
    if not row:
        raise HTTPException(404, "SN 记录不存在")
    return row


@router.post("", status_code=201)
def create(body: SnLibraryIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        row = sn_library_store.create_record(body.model_dump(), actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    permission_guard.write_audit(db, actor, "sn_library.create", row["sn"], row.get("product", ""), commit=True)
    return row


@router.put("/{record_id}")
def update(record_id: str, body: SnLibraryIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        row = sn_library_store.update_record(record_id, body.model_dump(), actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    permission_guard.write_audit(db, actor, "sn_library.update", row["sn"], row.get("product", ""), commit=True)
    return row


@router.delete("/{record_id}")
def delete(record_id: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        row = sn_library_store.delete_record(record_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    permission_guard.write_audit(db, actor, "sn_library.delete", row["sn"], row.get("product", ""), commit=True)
    return row
