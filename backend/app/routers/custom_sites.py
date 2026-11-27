"""自定义站点与访问流程管理接口。"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, custom_site_store, deps, models

class SiteIn(BaseModel):
    name: str
    url: str
    description: str = ""
    icon: str = "◇"
    groupId: str = ""
    order: int = 1
    enabled: bool = True
    access: dict = {}
    flow: dict = {}


class GroupIn(BaseModel):
    name: str
    description: str = ""
    order: int = 1


class FlowIn(BaseModel):
    name: str
    description: str = ""
    siteIds: list[str] = []
    access: dict = {}
    enabled: bool = True
    order: int = 1


get_db = deps.get_db


router = APIRouter(
    prefix="/api/custom-sites", tags=["自定义站点"],
    dependencies=[Depends(auth.current_account)],
)


def _identity(db: Session, account: models.Account):
    username = account.username
    perms = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    can_manage = bool(perms.intersection({"system:access:manage", "system:role:manage"}))
    return username, account.role or "", can_manage


def _require_manage(db: Session, account: models.Account):
    username, role, can_manage = _identity(db, account)
    if not can_manage:
        raise HTTPException(403, "当前账号无自定义站点管理权限")
    return username


@router.get("")
def config(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    username, role, can_manage = _identity(db, account)
    return {
        **custom_site_store.visible_config(custom_site_store.load_config(), username, role, can_manage),
        "canManage": can_manage,
        "username": username,
        "role": role,
    }


@router.post("/sites", status_code=201)
def create_site(body: SiteIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        return custom_site_store.create_site(body.model_dump(), db, actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/sites/{site_id}")
def update_site(site_id: str, body: SiteIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        return custom_site_store.update_site(site_id, body.model_dump(), db, actor)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/sites/{site_id}")
def delete_site(site_id: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        custom_site_store.delete_site(site_id, db, actor)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/groups", status_code=201)
def create_group(body: GroupIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        return custom_site_store.create_group(body.model_dump(), db, actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/groups/{group_id}")
def update_group(group_id: str, body: GroupIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        return custom_site_store.update_group(group_id, body.model_dump(), db, actor)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/groups/{group_id}")
def delete_group(group_id: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        custom_site_store.delete_group(group_id, db, actor)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/flows", status_code=201)
def create_flow(body: FlowIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        return custom_site_store.create_flow(body.model_dump(), db, actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/flows/{flow_id}")
def update_flow(flow_id: str, body: FlowIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        return custom_site_store.update_flow(flow_id, body.model_dump(), db, actor)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/flows/{flow_id}")
def delete_flow(flow_id: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        custom_site_store.delete_flow(flow_id, db, actor)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/next")
def next_site(siteId: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    username, role, can_manage = _identity(db, account)
    target = custom_site_store.resolve_next(siteId, username, role, can_manage)
    return {"target": target}
