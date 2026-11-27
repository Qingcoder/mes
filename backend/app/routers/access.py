"""站点/流程访问权限管理接口。"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import access_control, auth, deps, models

router = APIRouter(
    prefix="/api/access", tags=["站点流程权限"], dependencies=[Depends(auth.current_account)],
)


class GrantIn(BaseModel):
    scopeType: str
    scopeValue: str
    targetType: str
    targetValue: str
    effect: str = "allow"
    actions: list[str] = []
    description: Optional[str] = None
    enabled: bool = True


get_db = deps.get_db


def _identity(db: Session, account: models.Account):
    username = account.username
    perms = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if "system:access:manage" not in perms and "system:role:manage" not in perms:
        raise HTTPException(403, "当前账号无权限管理站点与流程授权")
    return username


@router.get("/options")
def options(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _identity(db, account)
    stations = []
    for wo in db.query(models.WorkOrder).all():
        for code in (wo.stations or []):
            if code and code not in stations:
                stations.append(code)
    flows = []
    for wo in db.query(models.WorkOrder).all():
        codes = [c for c in (wo.stations or []) if c]
        if len(codes) >= 2:
            value = ">".join(codes[:2])
            if value not in flows:
                flows.append(value)
    return {
        "scopeTypes": [
            {"value": "station", "label": "站点"},
            {"value": "flow", "label": "流程"},
        ],
        "targetTypes": [
            {"value": "role", "label": "角色"},
            {"value": "user", "label": "用户"},
        ],
        "effects": [
            {"value": "allow", "label": "允许"},
            {"value": "deny", "label": "拒绝"},
        ],
        "actions": [
            {"value": "view", "label": "查看"},
            {"value": "operate", "label": "操作"},
        ],
        "stations": stations,
        "flows": flows,
        "roles": [{"value": r.code, "label": r.name} for r in db.query(models.Role).order_by(models.Role.code).all()],
        "users": [{"value": a.username, "label": a.name or a.username} for a in db.query(models.Account).order_by(models.Account.username).all()],
    }


@router.get("/grants")
def list_grants(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _identity(db, account)
    return {"items": access_control.current_grants(db)}


@router.post("/grants", status_code=201)
def create_grant(body: GrantIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _identity(db, account)
    try:
        return access_control.create_grant(db, body.model_dump(), actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/grants/{grant_id}")
def update_grant(grant_id: str, body: GrantIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _identity(db, account)
    try:
        return access_control.update_grant(db, grant_id, body.model_dump(), actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/grants/{grant_id}")
def delete_grant(grant_id: str, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _identity(db, account)
    try:
        access_control.delete_grant(db, grant_id, actor)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/check")
def check_access(
    scopeType: str = Query(...),
    scopeValue: str = Query(...),
    action: str = Query("view"),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    username = account.username
    return {
        "allowed": access_control.is_allowed(db, username, account.role, scopeType, scopeValue, action),
        "username": username,
        "role": account.role,
    }
