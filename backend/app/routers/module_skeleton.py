"""通用模块骨架接口：只负责空壳记录，不承载业务逻辑。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, module_skeleton_store

router = APIRouter(
    prefix="/api/module-skeleton", tags=["模块骨架"],
    dependencies=[Depends(auth.current_account)],
)


class RecordIn(BaseModel):
    data: dict = {}


get_db = deps.get_db


def _check_key(key: str) -> None:
    meta = module_skeleton_store.meta_of(key)
    if not meta:
        raise HTTPException(404, "模块骨架不存在")
    if meta.get("mode") != "skeleton":
        raise HTTPException(400, "该模块已有独立实现，请使用专属接口")


@router.get("/modules")
def modules():
    return {"items": module_skeleton_store.list_modules()}


@router.get("/{key}/meta")
def meta(key: str):
    _check_key(key)
    return module_skeleton_store.meta_of(key)


@router.get("/{key}/records")
def records(key: str):
    _check_key(key)
    items = module_skeleton_store.list_records(key)
    return {"items": items, "total": len(items)}


@router.post("/{key}/records", status_code=201)
def create_record(
    key: str,
    body: RecordIn,
    account=Depends(auth.current_account),
):
    _check_key(key)
    return module_skeleton_store.create_record(key, body.data, account.username)


@router.put("/{key}/records/{record_id}")
def update_record(
    key: str,
    record_id: str,
    body: RecordIn,
    account=Depends(auth.current_account),
):
    _check_key(key)
    try:
        return module_skeleton_store.update_record(key, record_id, body.data, account.username)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{key}/records/{record_id}")
def delete_record(key: str, record_id: str, account=Depends(auth.current_account)):
    _check_key(key)
    try:
        module_skeleton_store.delete_record(key, record_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
