"""产品资料接口。"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, models, permission_guard, product_profiles_store

router = APIRouter(
    prefix="/api/product-profiles", tags=["产品资料"],
    dependencies=[Depends(auth.current_account)],
)


get_db = deps.get_db


class SimpleProductIn(BaseModel):
    name: str = ""


class SimpleSnsIn(BaseModel):
    sns: List[str] = []


class SimpleNameIn(BaseModel):
    name: str = ""


def _require_write(db: Session, account: models.Account) -> str:
    codes = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if account.role != "admin" and not ({"wo:create", "material:manage"} & codes):
        raise HTTPException(403, "当前账号无产品资料维护权限")
    return account.username


def _handle(exc: Exception):
    raise HTTPException(400, str(exc))


def _sync_product_row(db: Session, code: str, name: str) -> None:
    code = str(code or "").strip().upper()
    row = db.query(models.Product).filter_by(code=code).first()
    if row:
        row.name = name
    else:
        db.add(models.Product(code=code, name=name))
    db.commit()


def _delete_product_row(db: Session, code: str) -> None:
    row = db.query(models.Product).filter_by(code=str(code or "").strip().upper()).first()
    if row:
        db.delete(row)
        db.commit()


def _ensure_profile(code: str, db: Session) -> None:
    """总表缺资料但数据库有该产品时，按数据库名称补建资料结构，避免导入被拒。"""
    key = str(code or "").strip().upper()
    if product_profiles_store.find_product_by_code(key):
        return
    row = db.query(models.Product).filter_by(code=key).first()
    if row:
        product_profiles_store.ensure_product_profile(key, row.name)


def _merged_products(db: Session) -> List[Dict[str, Any]]:
    profiles = {str(p.get("code", "")).upper(): p for p in product_profiles_store.list_profiles()}
    rows: List[Dict[str, Any]] = []
    db_rows = {p.code: p for p in db.query(models.Product).all()}
    for code, row in db_rows.items():
        profile = profiles.get(code)
        rows.append({
            "code": code,
            "name": profile.get("name") if profile else row.name,
            "family": profile.get("family", "") if profile else "",
            "batchDate": profile.get("batchDate", "") if profile else "",
            "hasProfile": bool(profile),
            "snCount": sum(len(s.get("sns") or []) for s in (profile or {}).get("sides", [])),
            "relatedStations": (profile or {}).get("relatedStations", []),
            "relatedEquipment": (profile or {}).get("relatedEquipment", []),
            "relatedPersons": (profile or {}).get("relatedPersons", []),
        })
    for code, profile in profiles.items():
        if code in db_rows:
            continue
        rows.append({
            "code": code,
            "name": profile.get("name", ""),
            "family": profile.get("family", ""),
            "batchDate": profile.get("batchDate", ""),
            "hasProfile": True,
            "snCount": sum(len(s.get("sns") or []) for s in profile.get("sides", [])),
        })
    return sorted(rows, key=lambda r: r["code"])


@router.get("")
def products(db: Session = Depends(get_db), _=Depends(auth.current_account)):
    return _merged_products(db)


@router.get("/lookup")
def lookup(sn: str, _=Depends(auth.current_account)):
    result = product_profiles_store.lookup_sn(sn)
    if not result:
        raise HTTPException(404, "该 SN 不属于已登记产品")
    return result


@router.get("/{code}")
def detail(code: str, db: Session = Depends(get_db), _=Depends(auth.current_account)):
    try:
        result = product_profiles_store.detail(code)
        result["hasProfile"] = True
        return result
    except ValueError:
        row = db.query(models.Product).filter_by(code=str(code or "").strip().upper()).first()
        if not row:
            raise HTTPException(404, "产品资料不存在")
        result = product_profiles_store.basic_product(row.code, row.name)
        result["hasProfile"] = False
        return result


@router.post("/simple", status_code=201)
def create_simple_product(
    body: SimpleProductIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        product = product_profiles_store.create_simple_product(str(body.name or "").strip())
    except (TypeError, ValueError) as exc:
        _handle(exc)
    _sync_product_row(db, product["code"], product["name"])
    permission_guard.write_audit(db, actor, "product.profile.simple.create", product["code"], product["name"], commit=True)
    return product


@router.put("/{code}/name")
def rename_simple_product(
    code: str,
    body: SimpleNameIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        _ensure_profile(code, db)
        product = product_profiles_store.rename_simple_product(code, str(body.name or "").strip())
    except (TypeError, ValueError) as exc:
        _handle(exc)
    _sync_product_row(db, product["code"], product["name"])
    permission_guard.write_audit(db, actor, "product.profile.simple.rename", code, product["name"], commit=True)
    return product


@router.post("/{code}/sns/import")
def import_simple_sns(
    code: str,
    body: SimpleSnsIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        _ensure_profile(code, db)
        product = product_profiles_store.import_simple_sns(code, body.sns)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "product.sn.simple.import", code, f"created={product['createdCount']}; skipped={product['skippedCount']}", commit=True)
    return product


@router.post("/batch")
def create_products_batch(
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    family = str(payload.get("family") or "").strip()
    name_prefix = str(payload.get("namePrefix") or family or "产品").strip()
    code_prefix = str(payload.get("codePrefix") or "").strip().upper()
    if not family or not name_prefix:
        raise HTTPException(400, "系列名称和产品名称前缀不能为空")
    if not product_profiles_store.PRODUCT_CODE_RE.fullmatch(code_prefix):
        raise HTTPException(400, "产品编码前缀需以大写字母开头，仅含大写字母、数字、下划线或短横线")
    left_prefix = str(payload.get("leftPrefix") or "").strip().upper() or (code_prefix + "Z")
    right_prefix = str(payload.get("rightPrefix") or "").strip().upper() or (code_prefix + "Y")
    if len(left_prefix) > 16 or len(right_prefix) > 16:
        raise HTTPException(400, "左右件 SN 前缀不能超过 16 字符")
    try:
        count = int(payload.get("count") or 0)
        start = int(payload.get("start") or 1)
        step = int(payload.get("step") or 1)
    except (TypeError, ValueError):
        raise HTTPException(400, "数量、起始序号和步长必须是数字")
    if count < 1 or count > 100:
        raise HTTPException(400, "单次生成数量必须在 1-100 之间")
    if start < 0 or step < 1:
        raise HTTPException(400, "起始序号不能为负，步长必须大于 0")
    digits = max(3, len(str(start + (count - 1) * step)))
    items: List[Dict[str, Any]] = []
    for index in range(count):
        number = start + index * step
        code = f"{code_prefix}{str(number).zfill(digits)}"
        items.append({
            "code": code,
            "name": f"{name_prefix}{number}",
            "family": family,
            "description": str(payload.get("description") or "").strip(),
            "batchDate": str(payload.get("batchDate") or "").strip(),
            "sourceFiles": [],
            "snRule": {
                "length": 16,
                "leftPrefix": left_prefix,
                "rightPrefix": right_prefix,
                "sideBy": "SN 前缀",
            },
            "specs": [], "functions": [], "scenarios": [],
            "sides": [
                {"key": "left", "name": "左件", "prefix": left_prefix, "fileName": "", "sns": []},
                {"key": "right", "name": "右件", "prefix": right_prefix, "fileName": "", "sns": []},
            ],
        })
    try:
        products = product_profiles_store.create_products_batch(items)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    for product in products:
        _sync_product_row(db, product["code"], product["name"])
    permission_guard.write_audit(db, actor, "product.profile.batch", family, f"count={len(products)}", commit=True)
    return products


@router.post("")
def create_product(
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        product = product_profiles_store.create_product(payload)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    _sync_product_row(db, product["code"], product["name"])
    permission_guard.write_audit(db, actor, "product.profile.create", product["code"], product["name"], commit=True)
    return product


@router.put("/{code}")
def update_product(
    code: str,
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        product = product_profiles_store.update_product(code, payload)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    _sync_product_row(db, product["code"], product["name"])
    permission_guard.write_audit(db, actor, "product.profile.update", code, product["name"], commit=True)
    return product


@router.delete("/{code}")
def delete_product(
    code: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        removed = product_profiles_store.delete_product(code)
    except ValueError as exc:
        _handle(exc)
    if not removed and not db.query(models.Product).filter_by(code=str(code or "").strip().upper()).first():
        raise HTTPException(404, "产品资料不存在")
    _delete_product_row(db, code)
    permission_guard.write_audit(db, actor, "product.profile.delete", code, "", commit=True)
    return {"ok": True}


@router.post("/{code}/sns")
def add_sns(
    code: str,
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        _ensure_profile(code, db)
        product = product_profiles_store.add_sns(code, payload.get("sns") or [], str(payload.get("sideKey") or ""))
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "product.sn.create", code, f"count={len(payload.get('sns') or [])}", commit=True)
    return product


@router.put("/{code}/sns/{sn}")
def update_sn(
    code: str,
    sn: str,
    payload: dict,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        product = product_profiles_store.update_sn(code, sn, payload.get("sn") or sn, str(payload.get("sideKey") or ""))
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "product.sn.update", code, f"{sn}->{payload.get('sn') or sn}", commit=True)
    return product


@router.post("/{code}/sns/delete")
def delete_sns(
    code: str,
    body: SimpleSnsIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    sns = [str(sn).strip().upper() for sn in (body.sns or []) if str(sn).strip()]
    try:
        result = product_profiles_store.delete_sns(code, sns)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(
        db, actor, "product.sn.delete.batch", code,
        f"count={result['removedCount']}; sns={','.join(result['removed'][:20])}", commit=True,
    )
    return result


@router.delete("/{code}/sns/{sn}")
def delete_sn(
    code: str,
    sn: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_write(db, account)
    try:
        product = product_profiles_store.delete_sn(code, sn)
    except (TypeError, ValueError) as exc:
        _handle(exc)
    permission_guard.write_audit(db, actor, "product.sn.delete", code, sn, commit=True)
    return product
