"""当前登录账号的个人资料与密码维护。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, models, personnel_store, permission_guard

get_db = deps.get_db

router = APIRouter(
    prefix="/api/account", tags=["当前账号"],
    dependencies=[Depends(auth.current_account)],
)


class ProfileIn(BaseModel):
    name: str = ""
    avatar: str = ""


class PasswordIn(BaseModel):
    currentPassword: str = ""
    newPassword: str = ""


def _profile(account: models.Account) -> dict:
    return {
        "username": account.username,
        "name": account.name or account.username,
        "role": account.role or "",
        "avatar": account.avatar or "",
    }


@router.get("/profile")
def profile(account: models.Account = Depends(auth.current_account)):
    return _profile(account)


@router.put("/profile")
def update_profile(
    body: ProfileIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = account.username
    target = db.query(models.Account).filter_by(username=actor).first()
    if not target:
        raise HTTPException(404, "当前账号不存在")
    name = str(body.name or target.name or actor).strip()
    avatar = str(body.avatar or "").strip()
    if not name:
        raise HTTPException(400, "姓名不能为空")
    if len(name) > 64:
        raise HTTPException(400, "姓名不能超过 64 字符")
    if len(avatar) > 4:
        raise HTTPException(400, "头像标识不能超过 4 字符")
    target.name = name
    target.avatar = avatar
    db.commit()
    personnel_store.sync_name(actor, name, actor)
    permission_guard.write_audit(db, actor, "account.profile.update", actor, name, commit=True)
    return _profile(target)


@router.post("/password")
def change_password(
    body: PasswordIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = account.username
    target = db.query(models.Account).filter_by(username=actor).first()
    if not target:
        raise HTTPException(404, "当前账号不存在")
    current = str(body.currentPassword or "")
    new = str(body.newPassword or "").strip()
    if not auth.verify_password(current, target.password or ""):
        raise HTTPException(400, "当前密码不正确")
    if len(new) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    if auth.verify_password(new, target.password or ""):
        raise HTTPException(400, "新密码不能与当前密码相同")
    target.password = auth.hash_password(new)
    db.commit()
    permission_guard.write_audit(db, actor, "account.password.change", actor, "", commit=True)
    return {"ok": True, "message": "密码已修改，下次登录请使用新密码"}
