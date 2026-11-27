"""统一功能树接口：读取树与生成权限/路由配置。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, function_tree_store, models

router = APIRouter(
    prefix="/api/function-tree", tags=["功能树"],
    dependencies=[Depends(auth.current_account)],
)


class ApplyIn(BaseModel):
    functions: list[str] = []


get_db = deps.get_db


def _require_manage(db: Session, account) -> None:
    perms = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if not perms.intersection({"system:role:manage", "system:access:manage"}):
        raise HTTPException(403, "当前账号无功能配置权限")


@router.get("")
def tree():
    return function_tree_store.load_tree()


@router.get("/routes")
def routes():
    return function_tree_store.load_route_config()


@router.get("/module-registry")
def module_registry():
    registry = function_tree_store.load_module_registry()
    return {
        "version": registry.get("version", 1),
        "codePrefix": registry.get("codePrefix", "RB"),
        "permissionOrder": function_tree_store.combo_permission_order(),
        "functionOrder": function_tree_store.combo_function_order(),
        "modules": function_tree_store.combo_modules([]),
    }


@router.get("/templates")
def templates():
    config = function_tree_store.load_templates()
    known = function_tree_store.known_function_ids()
    items = []
    for item in config.get("items", []):
        functions = [x for x in item.get("functions", []) if x in known]
        items.append({
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "avatar": item.get("avatar", ""),
            "custom": bool(item.get("custom", False)),
            "functions": functions,
        })
    return {"version": config.get("version", 1), "items": items}


@router.post("/apply")
def apply(body: ApplyIn, account=Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    try:
        config = function_tree_store.apply_selected(body.functions, db, account.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.commit()
    return config
