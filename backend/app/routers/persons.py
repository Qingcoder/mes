"""人员模块接口。

- accounts 表：登录身份、角色、密码。
- personnel.json：部门、岗位、电话、状态、备注等人员扩展信息。
- 权限边界：维护人员需要系统用户/角色管理权限；全局模块可通过 options 接口读取轻量人员字典。
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, models, permission_guard, personnel_store, relation_store

router = APIRouter(
    prefix="/api/persons", tags=["人员模块"],
    dependencies=[Depends(auth.current_account)],
)


class PositionRenameIn(BaseModel):
    oldPosition: str
    newPosition: str


class PersonRoleIn(BaseModel):
    role: str


class PersonPermissionsIn(BaseModel):
    permissions: List[str] = []


class PersonIn(BaseModel):
    username: str
    password: str = ""
    name: str = ""
    role: str = ""
    department: str = ""
    position: str = ""
    parentUsername: str = ""
    phone: str = ""
    status: str = "active"
    moduleGrants: dict = {}
    relatedStations: List[Any] = []
    relatedProducts: List[Any] = []
    relatedEquipment: List[Any] = []
    notes: str = ""


get_db = deps.get_db


MODULE_PARENT_PERMISSIONS = {
    "dashboard:view", "person:manage", "machine:manage",
    "material:manage", "method:manage", "environment:manage",
}


def _held_permissions(db: Session, account: models.Account) -> set[str]:
    return {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}


def _require_manage(db: Session, account: models.Account) -> None:
    """维护权限：新增/编辑人员、分配角色与权限需要用户或角色管理权。"""
    if not _held_permissions(db, account).intersection({"system:user:manage", "system:role:manage"}):
        raise HTTPException(403, "当前账号无人员管理权限")


def _require_view(db: Session, account: models.Account) -> None:
    """查看权限：持有人员模块访问权（person:manage）即可查看，写操作仍需维护权限。

    菜单可见性由 person:manage 决定，若读取也要求 system:* 会出现
    “菜单看得见、页面全是 403”的死路，因此读与写分两层校验。
    """
    if not _held_permissions(db, account).intersection(
        {"person:manage", "system:user:manage", "system:role:manage"}
    ):
        raise HTTPException(403, "当前账号无人员查看权限")


def _delegable_module_permissions(db: Session, account: models.Account) -> set[str]:
    held = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    return held.intersection(MODULE_PARENT_PERMISSIONS)


def _delegable_person_permissions(db: Session, account: models.Account) -> set[str]:
    held = set(personnel_store.effective_permissions(db, account.username, account.role))
    return held.intersection(personnel_store.assignable_permission_codes())


def _validate_parent(db: Session, username: str, parent: str) -> None:
    parent = (parent or "").strip()
    if not parent:
        return
    if parent == username:
        raise HTTPException(400, "上级不能是自己")
    if not db.query(models.Account).filter_by(username=parent).first():
        raise HTTPException(400, "上级人员不存在")
    persons = personnel_store.list_persons()
    by_username = {p.get("username"): p for p in persons}
    seen = {username}
    cursor = parent
    while cursor and cursor in by_username:
        if cursor in seen:
            raise HTTPException(400, "上下级关系不能形成循环")
        seen.add(cursor)
        cursor = (by_username.get(cursor) or {}).get("parentUsername", "")


def _subordinates(username: str) -> list[dict]:
    return [
        {
            "username": p.get("username", ""),
            "department": p.get("department", ""),
            "position": p.get("position", ""),
        }
        for p in personnel_store.list_persons()
        if (p.get("parentUsername") or "").strip() == username
    ]


def _perms_of(db: Session, username: str) -> list[str]:
    account = db.query(models.Account).filter_by(username=username).first()
    if not account:
        return []
    return personnel_store.effective_permissions(db, username, account.role)


def _merge(db: Session, meta: dict) -> dict:
    account = db.query(models.Account).filter_by(username=meta.get("username", "")).first()
    result = {
        **meta,
        "name": account.name if account else meta.get("name", ""),
        "role": account.role if account else "",
        "avatar": account.avatar if account else "",
        "permissions": _perms_of(db, meta.get("username", "")),
        "subordinates": _subordinates(meta.get("username", "")),
    }
    return relation_store.enrich_person(result, db)


@router.get("")
def list_people(
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_view(db, account)
    return {"items": [_merge(db, p) for p in personnel_store.list_persons()]}


@router.get("/options")
def person_options(
    _account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    """全局管理模块可读取的轻量人员字典。"""
    items = []
    for p in personnel_store.list_persons():
        username = p.get("username", "")
        account = db.query(models.Account).filter_by(username=username).first()
        items.append({
            "username": username,
            "name": account.name if account else "",
            "department": p.get("department", ""),
            "position": p.get("position", ""),
            "parentUsername": p.get("parentUsername", ""),
            "status": p.get("status", "active"),
            "moduleGrants": p.get("moduleGrants", {}),
            "subordinates": _subordinates(username),
        })
    return {"items": items}


@router.post("", status_code=201)
def create_person(
    body: PersonIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    username = body.username.strip()
    password = body.password.strip()
    role_code = body.role.strip()
    if not username or len(password) < 6:
        raise HTTPException(400, "用户名和密码必填，密码至少 6 位")
    if db.query(models.Account).filter_by(username=username).first():
        raise HTTPException(400, "登录账号已存在")
    if not db.query(models.Role).filter_by(code=role_code).first():
        raise HTTPException(404, "角色不存在")
    if role_code == "admin":
        raise HTTPException(400, "不允许通过人员模块创建管理员账号")
    payload = body.model_dump()
    if not str(payload.get("parentUsername") or "").strip():
        payload["parentUsername"] = account.username
    _validate_parent(db, username, payload["parentUsername"])
    name = body.name.strip() or username
    try:
        meta = personnel_store.create_person(payload, db, account.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    relation_store.apply_full_selection("person", username, payload, db)
    relation_store.sync_all(db)
    db.add(models.Account(
        username=username, password=auth.hash_password(password),
        name=name, role=role_code, avatar=name[:1],
    ))
    db.commit()
    return _merge(db, meta)


@router.put("/position/rename")
def rename_position(
    body: PositionRenameIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    try:
        return personnel_store.rename_position(body.oldPosition, body.newPosition, db, account.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/{username}/role")
def update_person_role(
    username: str,
    body: PersonRoleIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    target = db.query(models.Account).filter_by(username=username).first()
    if not target:
        raise HTTPException(404, "账号不存在")
    if target.role == "admin":
        raise HTTPException(400, "系统管理员角色不可变更")
    role_code = (body.role or "").strip()
    role = db.query(models.Role).filter_by(code=role_code).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    if role_code == "admin":
        raise HTTPException(400, "不能将人员设置为系统管理员")
    target_perms = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=role_code).all()}
    allowed = _delegable_module_permissions(db, account)
    if not target_perms.issubset(allowed):
        raise HTTPException(403, "当前账号不能分配该角色")
    old_role = target.role
    target.role = role_code
    permission_guard.write_audit(
        db, account.username, "person.role.update", username,
        f"from={old_role}; to={role_code}; perms={','.join(sorted(target_perms))}", commit=True,
    )
    return {"ok": True, "username": username, "role": role_code, "permissions": sorted(target_perms)}


@router.put("/{username}")
def update_person(
    username: str,
    body: PersonIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    payload = body.model_dump()
    payload["username"] = username
    _validate_parent(db, username, body.parentUsername)
    try:
        meta = personnel_store.update_person(payload, db, account.username)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    relation_store.apply_full_selection("person", username, payload, db)
    relation_store.sync_all(db)
    target = db.query(models.Account).filter_by(username=username).first()
    new_password = (body.password or "").strip()
    if new_password and len(new_password) < 6:
        raise HTTPException(400, "重置密码至少 6 位")
    if target:
        if body.name.strip():
            target.name = body.name.strip()
        if new_password:
            target.password = auth.hash_password(new_password)
        db.commit()
    if new_password:
        permission_guard.write_audit(db, account.username, "person.password.reset", username, "", commit=True)
    return _merge(db, meta)


@router.put("/{username}/permissions")
def save_person_permissions(
    username: str,
    body: PersonPermissionsIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    target = db.query(models.Account).filter_by(username=username).first()
    if not target:
        raise HTTPException(404, "账号不存在")
    if target.role == "admin":
        raise HTTPException(400, "系统管理员权限不可变更")
    allowed = _delegable_person_permissions(db, account)
    wanted = {str(code).strip() for code in body.permissions if str(code).strip()}
    denied = wanted - allowed
    if denied:
        raise HTTPException(403, "当前账号不能分配未持有的权限：" + ", ".join(sorted(denied)))
    try:
        permissions = personnel_store.set_permission_override(username, sorted(wanted), db, account.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "username": username, "permissions": permissions}


@router.get("/{username}/permissions")
def person_permissions(
    username: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_view(db, account)
    perms = _perms_of(db, username)
    return {"username": username, "permissions": perms}


@router.get("/{username}/scope")
def person_scope(
    username: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    """供四大模块调用：获取某人员的组织位置、角色权限与模块统筹权限。"""
    _require_view(db, account)
    meta = personnel_store.get_person(username)
    if not meta:
        raise HTTPException(404, "人员记录不存在")
    return {
        **_merge(db, meta),
        "scope": {
            "department": meta.get("department", ""),
            "position": meta.get("position", ""),
            "parentUsername": meta.get("parentUsername", ""),
            "subordinates": _subordinates(username),
            "rolePermissions": _perms_of(db, username),
            "moduleGrants": meta.get("moduleGrants", {}),
        },
    }
