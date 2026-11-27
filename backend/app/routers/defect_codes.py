"""不良代码库接口。"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, defect_code_store, models, permission_guard, process_design_store, product_profiles_store

router = APIRouter(
    prefix="/api/defect-codes", tags=["不良代码库"],
    dependencies=[Depends(auth.current_account)],
)


class DefectCodeIn(BaseModel):
    code: str = ""
    name: str = ""
    productCode: str = ""
    productName: str = ""
    stationCode: str = ""
    stationName: str = ""
    repairMethod: str = ""
    description: str = ""


class DefectImportIn(BaseModel):
    rows: List[dict] = []


get_db = deps.get_db


def _require_manage(db: Session, account: models.Account) -> str:
    codes = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if account.role != "admin" and "method:manage" not in codes:
        raise HTTPException(403, "当前账号无工艺管理权限")
    return account.username


@router.get("")
def list_codes(
    keyword: str = "", productCode: str = "", stationCode: str = "", repairMethod: str = "",
    _account: models.Account = Depends(auth.current_account),
):
    return defect_code_store.list_codes(keyword, productCode, stationCode, repairMethod)


@router.get("/options")
def options(
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    config = process_design_store.load_config()
    stations = [
        {"code": str(row.get("code") or ""), "name": str(row.get("name") or row.get("code") or "")}
        for row in config.get("stations", []) if row.get("code")
    ]
    products = [
        {"code": str(row.get("code") or ""), "name": str(row.get("name") or row.get("code") or "")}
        for row in product_profiles_store.list_profiles() if row.get("code")
    ]
    return {
        "products": products,
        "stations": stations,
        "repairMethods": defect_code_store.REPAIR_METHODS,
    }


@router.get("/template")
def template(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    return Response(
        content=defect_code_store.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="defect_codes_template.csv"'},
    )


@router.post("", status_code=201)
def create_code(
    body: DefectCodeIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        row = defect_code_store.create_code(body.model_dump(), actor)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    permission_guard.write_audit(db, actor, "defect.code.create", row["code"], row["name"], commit=True)
    return row


@router.post("/import")
def import_codes(
    body: DefectImportIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    result = defect_code_store.import_rows(body.rows, actor)
    permission_guard.write_audit(
        db, actor, "defect.code.import", "defect_codes",
        f"created={result['created']}; reused={result['reused']}; failed={len(result['failed'])}", commit=True,
    )
    return result


@router.put("/{code}")
def update_code(
    code: str, body: DefectCodeIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        row = defect_code_store.update_code(code, body.model_dump(), actor)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    permission_guard.write_audit(db, actor, "defect.code.update", code, row["name"], commit=True)
    return row


@router.delete("/{code}")
def delete_code(
    code: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    if not defect_code_store.delete_code(code):
        raise HTTPException(404, "不良代码不存在")
    permission_guard.write_audit(db, actor, "defect.code.delete", code, "", commit=True)
    return {"ok": True}
