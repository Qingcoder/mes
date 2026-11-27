"""角色管理：角色 CRUD、权限点查询与角色权限分配。

复用既有 roles / permissions / role_permissions 表，不新增数据库结构。
所有接口走 demo-token 鉴权；真实用户级鉴权需在 JWT 改造后补充。
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from .. import auth, deps, function_tree_store, models, permission_guard, permission_registry, personnel_store, role_meta_store
from ..schemas import AuditOut, UserIn as AccountIn


router = APIRouter(
    prefix="/api", tags=["角色管理"], dependencies=[Depends(auth.current_account)],
)

# 新建自定义角色默认继承的权限（与 main.DEFAULT_ROLE_PERMS 保持一致）
DEFAULT_PERM_CODES = [
    "wo:view", "wo:create", "sn:import", "station:op",
    "rework:op", "pack:op", "query:view",
]

def perm_mode_code(permissions) -> str:
    """按权限项数量生成 PM 数码；顺序无关，未知权限不再被静默忽略。"""
    try:
        return permission_registry.permission_combo_code(permissions)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def level_of_action(action: str) -> str:
    """由动作码派生日志级别，避免新增字段。"""
    code = (action or "").lower()
    if "reject" in code or "fail" in code or "error" in code:
        return "ERROR"
    if "rework" in code or "hold" in code:
        return "WARN"
    return "INFO"


get_db = deps.get_db

MODULE_PARENT_PERMISSIONS = (
    "dashboard:view", "person:manage", "machine:manage",
    "material:manage", "method:manage", "environment:manage",
)


def _delegable_permissions(db: Session, actor: str) -> set[str]:
    """当前账号可继续下放的模块父权限；管理员按全部模块父权限处理。"""
    account = db.query(models.Account).filter_by(username=actor).first()
    if not account:
        raise HTTPException(403, "无法识别当前账号")
    if account.role == "admin":
        return set(MODULE_PARENT_PERMISSIONS)
    held = {row.perm_code for row in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    return held.intersection(MODULE_PARENT_PERMISSIONS)


def _assert_delegable(db: Session, actor: str, permissions) -> None:
    allowed = _delegable_permissions(db, actor)
    denied = sorted(set(permissions or []) - allowed)
    if denied:
        raise HTTPException(403, "当前账号不能分配未持有的权限：" + ", ".join(denied))


def _parent_permissions_for_functions(function_ids) -> list[str]:
    wanted = set(function_ids or [])
    function_tree_store.build_config(list(wanted), "admin")
    result: list[str] = []
    for module in function_tree_store.load_module_registry().get("modules", []):
        module_permission = module.get("permission")
        if module_permission not in MODULE_PARENT_PERMISSIONS:
            continue
        if module.get("functionId") in wanted:
            result.append(module_permission)
            continue
        if any(child.get("id") in wanted for child in function_tree_store._module_children(module.get("key", ""))):
            result.append(module_permission)
    return list(dict.fromkeys(result))


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PermOut(ORMModel):
    code: str
    name: str
    module: str


class RoleIn(BaseModel):
    code: Optional[str] = None
    name: str
    description: str = ""
    avatar: str = ""
    accountType: str = ""
    functions: Optional[List[str]] = None
    permissions: Optional[List[str]] = None


class RoleUpdateIn(BaseModel):
    name: str
    description: str = ""
    accountType: str = ""


class RolePermIn(BaseModel):
    permissions: List[str] = []


class RoleCombinationIn(BaseModel):
    modules: List[str] = []
    functions: List[str] = []
    name: str = ""
    avatar: str = ""


class RoleOut(BaseModel):
    code: str
    name: str
    description: str = ""
    avatar: str = ""
    accountType: str = ""
    builtin: bool = False
    user_count: int = 0
    accounts: List[str] = []
    created_by: str = ""
    permissions: List[str] = []
    perm_mode_code: str = ""
    combination: dict = {}


class PermTableItem(BaseModel):
    code: str
    name: str
    module: str
    weight: int
    role_count: int
    roles: List[str] = []


class PermTableOut(BaseModel):
    updated_at: str
    items: List[PermTableItem] = []


class SNLogOut(AuditOut):
    level: str = "INFO"


class SNLogPage(BaseModel):
    items: List[SNLogOut] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    sort: str = "desc"
    match: str = "exact"


def _infer_account_type(role: models.Role, perms: list[str]) -> str:
    """按角色名称和权限推断账户类别，角色元数据已有明确类别时优先使用。"""
    name = str(role.name or "")
    if role.code == "admin" or str(role.builtin).lower() == "true" and "admin" in name.lower():
        return "管理员"
    if "访客" in name or "guest" in name.lower():
        return "访客"
    if any(word in name for word in ("主管", "管理", "班长")):
        return "生产管理"
    if any(word in name for word in ("工程", "工艺", "技术", "维护", "设备")):
        return "工程维护"
    if any(word in name for word in ("工位", "站点", "作业", "测试", "产线")):
        return "现场作业"
    if any(code in perms for code in ("station:op", "rework:op", "pack:op")):
        return "现场作业"
    if any(code in perms for code in ("wo:create", "sn:import")):
        return "生产管理"
    if any(code.endswith(":manage") for code in perms):
        return "工程维护"
    return "其他"


def _role_out(db: Session, role: models.Role) -> RoleOut:
    perms = [r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=role.code).all()]
    account_rows = db.query(models.Account.username).filter_by(role=role.code).all()
    accounts = [row[0] for row in account_rows]
    creator_row = db.query(models.AuditLog.username).filter(
        models.AuditLog.action == "role.create",
        models.AuditLog.target == role.code,
    ).order_by(models.AuditLog.id.desc()).first()
    combo = role_meta_store.get_combination(role.code)
    if not combo and str(role.code).startswith("RB-"):
        module_rows = function_tree_store.combo_modules_by_permissions(perms)
        if module_rows:
            routes = function_tree_store.load_route_config()
            combo = {
                "code": role.code,
                "name": role.name,
                "modules": module_rows,
                "permissions": sorted(perms),
                "routes": routes.get("routes", []),
                "functions": routes.get("functions", []),
                "moduleKeys": [m["key"] for m in module_rows],
            }
    return RoleOut(
        code=role.code, name=role.name, description=role.description or "",
        avatar=role_meta_store.get_avatar(role.code),
        accountType=role_meta_store.get_account_type(role.code) or _infer_account_type(role, perms),
        builtin=bool(role.builtin), user_count=len(accounts), accounts=accounts,
        created_by=creator_row[0] if creator_row else "",
        permissions=sorted(perms), perm_mode_code=perm_mode_code(perms),
        combination=combo,
    )


def next_role_code(db: Session) -> str:
    """生成下一个可用角色编码 role_001 / role_002 ...，避开内置编码。"""
    prefix = "role_"
    nums = []
    for row in db.query(models.Role.code).all():
        code = str(row[0] or "")
        if code.startswith(prefix) and code[len(prefix):].isdigit():
            nums.append(int(code[len(prefix):]))
    return prefix + f"{max(nums) + 1 if nums else 1:03d}"


@router.get("/roles/next-code")
def get_next_role_code(db: Session = Depends(get_db)):
    return {"code": next_role_code(db)}


@router.get("/permissions", response_model=List[PermOut])
def list_permissions(db: Session = Depends(get_db)):
    registry = {p["code"]: p for p in permission_registry.permission_rows()}
    rows = db.query(models.Permission).order_by(models.Permission.module, models.Permission.code).all()
    return [
        PermOut(
            code=row.code,
            name=registry.get(row.code, {}).get("name", row.name),
            module=registry.get(row.code, {}).get("module", row.module),
        )
        for row in rows
    ]


@router.get("/permission-map")
def permission_map(db: Session = Depends(get_db)):
    """权限码对照：PM 数码按权限项数量生成，不再依赖权限顺序。"""
    return {
        "rule": {"format": "PM-<count:03d>", "order_independent": True, "unique_permission_set": False},
        "items": [
            {
                "old_code": row["code"],
                "new_code": row["code"],
                "name": row.get("name", row["code"]),
                "module": row.get("module", ""),
                "combined_code_if_alone": perm_mode_code([row["code"]]),
            }
            for row in permission_registry.permission_rows()
            if db.query(models.Permission).filter_by(code=row["code"]).first()
        ],
    }


@router.get("/permission-table", response_model=PermTableOut)
def permission_table(db: Session = Depends(get_db)):
    """实时权限表：直接查 permissions / role_permissions / roles。"""
    roles = db.query(models.Role).all()
    role_names = {r.code: r.name for r in roles}
    items = []
    for p in db.query(models.Permission).order_by(models.Permission.module, models.Permission.code).all():
        assigned = [rp.role_code for rp in db.query(models.RolePermission).filter_by(perm_code=p.code).all()]
        items.append(PermTableItem(
            code=p.code, name=p.name, module=p.module,
            weight=PERM_WEIGHTS.get(p.code, 0),
            role_count=len(assigned),
            roles=[role_names.get(c, c) for c in assigned],
        ))
    return PermTableOut(updated_at=datetime.utcnow().isoformat() + "Z", items=items)


@router.get("/permission-audit", response_model=List[AuditOut])
def permission_audit(limit: int = 100, days: Optional[int] = None, db: Session = Depends(get_db)):
    """按需查询权限变更与被拦截操作的审计日志；不调用则不输出。"""
    query = db.query(models.AuditLog).filter(models.AuditLog.action.like("role.%"))
    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=min(max(days, 1), 365))
        query = query.filter(models.AuditLog.ts >= cutoff)
    return query.order_by(models.AuditLog.ts.desc()).limit(min(max(limit, 1), 1000)).all()


@router.delete("/permission-audit")
def cleanup_permission_audit(
    days: int = permission_guard.AUDIT_RETENTION_DAYS,
    db: Session = Depends(get_db),
    actor: str = Depends(permission_guard.actor_dep),
):
    """按保留期清理历史权限日志（默认 90 天），需显式调用。"""
    return permission_guard.cleanup_role_audit(db, actor, days)


@router.get("/me/permissions")
def my_permissions(
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    """当前登录令牌对应账号的角色与有效权限，用于前端菜单过滤。"""
    perms = personnel_store.effective_permissions(db, account.username, account.role)
    return {
        "username": account.username, "name": account.name,
        "role": account.role, "permissions": sorted(perms),
    }


@router.post("/accounts", status_code=201)
def create_account(payload: AccountIn, db: Session = Depends(get_db), actor: str = Depends(permission_guard.actor_dep)):
    """为已有角色创建登录账号；新建角色弹窗可复用此接口。"""
    username = (payload.username or "").strip()
    password = (payload.password or "").strip()
    role_code = (payload.role or "").strip()
    if not username or not password:
        raise HTTPException(400, "用户名和密码必填")
    if len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    if db.query(models.Account).filter_by(username=username).first():
        raise HTTPException(400, "用户名已存在")
    if not db.query(models.Role).filter_by(code=role_code).first():
        raise HTTPException(404, "角色不存在")
    if role_code == "admin":
        raise HTTPException(400, "不允许通过角色管理创建管理员账号")
    name = (payload.name or "").strip() or username
    account = models.Account(
        username=username, password=password, name=name, role=role_code,
        avatar=name[:1],
    )
    db.add(account)
    permission_guard.write_audit(db, actor, "account.create", username, f"role={role_code}; name={name}")
    db.commit()
    db.refresh(account)
    return {"ok": True, "username": account.username, "name": account.name, "role": account.role}


@router.get("/sn-logs", response_model=SNLogPage)
def sn_logs(
    sn: str = Query(..., min_length=1, max_length=64),
    match: str = Query("exact", pattern="^(exact|fuzzy)$"),
    level: Optional[str] = Query(None, pattern="^(INFO|WARN|ERROR)$"),
    from_ts: Optional[datetime] = Query(None),
    to_ts: Optional[datetime] = Query(None),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor: str = Depends(permission_guard.actor_dep),
):
    """复用 audit_logs 的 SN 日志查询：精确/模糊、时间范围、级别、分页排序。"""
    needle = (sn or "").strip()
    if not needle:
        raise HTTPException(400, "SN 不能为空")
    if from_ts and to_ts and from_ts > to_ts:
        raise HTTPException(400, "开始时间不能晚于结束时间")

    level_expr = case(
        (models.AuditLog.action.like("%rejected%"), "ERROR"),
        (models.AuditLog.action.like("%fail%"), "ERROR"),
        (models.AuditLog.action.like("%error%"), "ERROR"),
        (models.AuditLog.action.like("%rework%"), "WARN"),
        else_="INFO",
    )

    query = db.query(models.AuditLog)
    if match == "exact":
        query = query.filter(or_(
            models.AuditLog.target == needle,
            models.AuditLog.detail.like(f"%{needle}%"),
        ))
    else:
        escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.filter(or_(
            models.AuditLog.target.like(pattern, escape="\\"),
            models.AuditLog.detail.like(pattern, escape="\\"),
        ))

    if level:
        query = query.filter(level_expr == level)
    if from_ts:
        query = query.filter(models.AuditLog.ts >= from_ts)
    if to_ts:
        query = query.filter(models.AuditLog.ts <= to_ts)

    total = query.count()
    order_col = models.AuditLog.ts.asc() if sort == "asc" else models.AuditLog.ts.desc()
    rows = query.order_by(order_col, models.AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        SNLogOut(
            id=r.id, ts=r.ts, username=r.username, action=r.action,
            target=r.target, detail=r.detail, level=level_of_action(r.action),
        )
        for r in rows
    ]
    return SNLogPage(items=items, total=total, page=page, page_size=page_size, sort=sort, match=match)


@router.get("/roles", response_model=List[RoleOut])
def list_roles(keyword: str = "", db: Session = Depends(get_db)):
    q = db.query(models.Role)
    if keyword.strip():
        kw = "%" + keyword.strip() + "%"
        q = q.filter((models.Role.code.like(kw)) | (models.Role.name.like(kw)))
    return [_role_out(db, r) for r in q.order_by(models.Role.builtin.desc(), models.Role.id).all()
            if not role_meta_store.is_deleted(r.code)]


@router.post("/role-combinations")
def create_role_combination(payload: RoleCombinationIn, db: Session = Depends(get_db), actor: str = Depends(permission_guard.actor_dep)):
    modules = list(dict.fromkeys(payload.modules or []))
    function_ids = list(dict.fromkeys(payload.functions or []))
    module_rows = []
    if not modules and not function_ids:
        raise HTTPException(400, "至少选择一个模块权限")
    registry = {m["key"]: m["permission"] for m in function_tree_store.load_module_registry().get("modules", [])}
    parent_codes = [registry[key] for key in modules if key in registry]
    _assert_delegable(db, actor, parent_codes)
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "角色名称必填")

    try:
        code = function_tree_store.combo_code(modules, function_ids)
        module_rows = [m for m in function_tree_store.combo_modules(modules, function_ids) if m["selected"]]
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    existing = db.query(models.Role).filter_by(code=code).first()
    if existing:
        result = _role_out(db, existing).model_dump()
        result["created"] = False
        result["modules"] = module_rows
        if not result.get("combination"):
            combination = {
                "code": code,
                "name": existing.name,
                "modules": module_rows,
                "permissions": result.get("permissions", []),
                "routes": function_tree_store.load_route_config().get("routes", []),
                "functions": function_tree_store.load_route_config().get("functions", []),
                "moduleKeys": [m["key"] for m in module_rows],
                "functionIds": function_ids,
            }
            role_meta_store.set_combination(code, combination, actor)
            result["combination"] = combination
        return result

    duplicate_name = db.query(models.Role).filter(func.lower(models.Role.name) == name.lower()).first()
    if duplicate_name:
        raise HTTPException(400, f"角色名称已存在：{name}")

    selected_functions = list(dict.fromkeys([
        *[m["functionId"] for m in module_rows if m.get("functionId")],
        *function_ids,
    ]))
    function_config = function_tree_store.apply_selected(selected_functions, db, actor)
    granted = list(dict.fromkeys(
        p["code"] for p in function_config["permissions"]
        if p["code"] in parent_codes
    ))

    avatar = payload.avatar.strip()[:8] or name[:1]
    description = f"按模块组合自动生成：{','.join([m['key'] for m in module_rows])}；子权限：{','.join(function_ids) or '无'}"
    role = models.Role(code=code, name=name, description=description, builtin=False)
    db.add(role)
    db.flush()
    for pcode in granted:
        db.add(models.RolePermission(role_code=code, perm_code=pcode))
    permission_guard.write_audit(db, actor, "role.combination.create", code, f"name={name}; modules={','.join(modules)}; perms={','.join(granted)}")
    db.commit()
    db.refresh(role)
    role_meta_store.set_avatar(code, avatar, actor)
    combination = {
        "code": code,
        "name": name,
        "modules": module_rows,
        "permissions": granted,
        "routes": function_config.get("routes", []),
        "functions": function_config.get("functions", []),
        "moduleKeys": [m["key"] for m in module_rows],
        "functionIds": function_ids,
    }
    role_meta_store.set_combination(code, combination, actor)
    result = _role_out(db, role).model_dump()
    result["created"] = True
    result["modules"] = module_rows
    return result


@router.post("/roles", response_model=RoleOut)
def create_role(payload: RoleIn, db: Session = Depends(get_db), actor: str = Depends(permission_guard.actor_dep)):
    code = next_role_code(db)
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "角色名称必填")
    duplicate_name = db.query(models.Role).filter(
        func.lower(models.Role.name) == name.lower()
    ).first()
    if duplicate_name:
        raise HTTPException(400, f"角色名称已存在：{name}")
    if db.query(models.Role).filter_by(code=code).first():
        raise HTTPException(400, "角色编码已存在")
    avatar = payload.avatar.strip()[:8] or name[:1]
    role = models.Role(code=code, name=name, description=payload.description.strip(), builtin=False)
    db.add(role)
    db.flush()
    known = {p.code for p in db.query(models.Permission).all()}
    if payload.permissions is not None:
        wanted = set(payload.permissions)
        unknown = wanted - known
        if unknown:
            raise HTTPException(400, "未知权限：" + ", ".join(sorted(unknown)))
        granted = [pcode for pcode in payload.permissions if pcode in known]
    elif payload.functions is not None:
        granted = _parent_permissions_for_functions(payload.functions)
    else:
        granted = sorted(_delegable_permissions(db, actor))
    _assert_delegable(db, actor, granted)
    for pcode in granted:
        db.add(models.RolePermission(role_code=code, perm_code=pcode))
    permission_guard.write_audit(db, actor, "role.create", code, f"name={name}; perms={','.join(granted)}")
    db.commit()
    db.refresh(role)
    role_meta_store.set_avatar(code, avatar, actor)
    if payload.accountType.strip():
        role_meta_store.set_account_type(code, payload.accountType, actor)
    return _role_out(db, role)


@router.put("/roles/{code}", response_model=RoleOut)
def update_role(code: str, payload: RoleUpdateIn, db: Session = Depends(get_db), actor: str = Depends(permission_guard.actor_dep)):
    role = db.query(models.Role).filter_by(code=code).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    permission_guard.guard_role_mutable(db, role, actor, "role.update")
    if not payload.name.strip():
        raise HTTPException(400, "角色名称必填")
    role.name = payload.name.strip()
    role.description = payload.description.strip()
    combination = role_meta_store.get_combination(code)
    if combination:
        combination["name"] = role.name
        role_meta_store.set_combination(code, combination, actor)
    if payload.accountType.strip():
        role_meta_store.set_account_type(code, payload.accountType, actor)
    permission_guard.write_audit(db, actor, "role.update", code, f"name={role.name}; desc={role.description}; accountType={payload.accountType.strip()}")
    db.commit()
    db.refresh(role)
    return _role_out(db, role)


@router.delete("/roles/{code}")
def delete_role(code: str, db: Session = Depends(get_db), actor: str = Depends(permission_guard.actor_dep)):
    role = db.query(models.Role).filter_by(code=code).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    permission_guard.guard_role_mutable(db, role, actor, "role.delete")
    snapshot = _role_out(db, role).model_dump()
    role_meta_store.archive_deleted_role(code, snapshot, actor)
    permission_guard.write_audit(
        db, actor, "role.delete", code,
        f"name={role.name}; soft_delete=1; snapshot=role_meta; accounts={len(snapshot.get('accounts') or [])}",
        commit=True,
    )
    return {"ok": True, "softDelete": True, "restorable": True}


@router.post("/roles/{code}/restore")
def restore_role(code: str, db: Session = Depends(get_db), actor: str = Depends(permission_guard.actor_dep)):
    role = db.query(models.Role).filter_by(code=code).first()
    if not role:
        raise HTTPException(404, "角色记录不存在，无法恢复")
    permission_guard.guard_role_mutable(db, role, actor, "role.restore")
    snapshot = role_meta_store.get_deleted_snapshot(code)
    if snapshot:
        role.name = str(snapshot.get("name") or role.name)
        role.description = str(snapshot.get("description") or "")
        role.builtin = bool(snapshot.get("builtin"))
        known = {p.code for p in db.query(models.Permission).all()}
        wanted = sorted(set(snapshot.get("permissions") or []) & known)
        db.query(models.RolePermission).filter_by(role_code=code).delete(synchronize_session=False)
        for pcode in wanted:
            db.add(models.RolePermission(role_code=code, perm_code=pcode))
    role_meta_store.restore_deleted_role(code, actor)
    permission_guard.write_audit(db, actor, "role.restore", code, f"name={role.name}; snapshot_restored={bool(snapshot)}")
    db.commit()
    return {"ok": True, "restored": True}


@router.get("/roles/{code}/permissions", response_model=List[str])
def role_permissions(code: str, db: Session = Depends(get_db)):
    if not db.query(models.Role).filter_by(code=code).first():
        raise HTTPException(404, "角色不存在")
    return [r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=code).all()]


@router.put("/roles/{code}/permissions")
def set_role_permissions(code: str, payload: RolePermIn, db: Session = Depends(get_db), actor: str = Depends(permission_guard.actor_dep)):
    role = db.query(models.Role).filter_by(code=code).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    wanted = set(payload.permissions or [])
    permission_guard.guard_permissions_mutable(db, role, actor, "role.permissions.update", wanted)
    known = {p.code for p in db.query(models.Permission).all()}
    unknown = wanted - known
    if unknown:
        raise HTTPException(400, "未知权限：" + ", ".join(sorted(unknown)))
    _assert_delegable(db, actor, wanted)
    db.query(models.RolePermission).filter_by(role_code=code).delete(synchronize_session=False)
    for pcode in sorted(wanted):
        db.add(models.RolePermission(role_code=code, perm_code=pcode))
    try:
        mode_code = perm_mode_code(sorted(wanted))
    except HTTPException:
        raise HTTPException(400, "权限组合包含未登记权限，请通过权限目录维护后再授权")
    permission_guard.write_audit(db, actor, "role.permissions.update", code, f"perms={','.join(sorted(wanted))}; mode={mode_code}")
    routes = function_tree_store.load_route_config()
    combination = role_meta_store.get_combination(code)
    if combination:
        combination["permissions"] = sorted(wanted)
        combination["modules"] = function_tree_store.combo_modules_by_permissions(sorted(wanted))
        combination["moduleKeys"] = [m["key"] for m in combination["modules"]]
        combination["routes"] = routes.get("routes", [])
        combination["functions"] = routes.get("functions", [])
        role_meta_store.set_combination(code, combination, actor)
    db.commit()
    return {"ok": True, "permissions": sorted(wanted), "permModeCode": perm_mode_code(sorted(wanted))}
