"""人机料法环领域配置接口。

仅保存用户编辑结果，不生成真实路由、菜单或权限逻辑。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, domain_config_store, models

router = APIRouter(
    prefix="/api/domain-config", tags=["人机料法环配置"],
    dependencies=[Depends(auth.current_account)],
)


class DomainConfigIn(BaseModel):
    domains: list[dict]


get_db = deps.get_db


def _can_manage(db: Session, account: models.Account) -> bool:
    perms = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    return bool(perms.intersection({"system:access:manage", "system:role:manage"}))


@router.get("")
def get_config(
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    return {
        **domain_config_store.load_config(),
        "canManage": _can_manage(db, account),
        "username": account.username,
        "role": account.role or "",
    }


@router.put("")
def save_config(
    body: DomainConfigIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    if not _can_manage(db, account):
        raise HTTPException(403, "当前账号无人机料法环配置权限")
    try:
        return domain_config_store.save_config(body.domains, db, account.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
