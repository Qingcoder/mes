"""人员扩展信息存储。

账号身份仍以 accounts 表为准；本文件只保存不属于登录身份的人员扩展字段，
避免新增数据库表结构。
"""
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from . import function_tree_store, permission_registry, relation_items
from .permission_guard import write_audit

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "personnel.json")
_LOCK = threading.Lock()
VERSION = 1


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


MODULE_PARENT_PERMISSIONS = {
    "dashboard:view", "person:manage", "machine:manage",
    "material:manage", "method:manage", "environment:manage",
}


def _default_config() -> Dict[str, Any]:
    return {"version": VERSION, "updatedAt": _now(), "persons": [], "permissionOverrides": {}}


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def _read_raw() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        config = _default_config()
        _write_raw(config)
        return config
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = _default_config()
        _write_raw(config)
    config.setdefault("version", VERSION)
    config.setdefault("persons", [])
    config.setdefault("updatedAt", _now())
    config.setdefault("permissionOverrides", {})
    return config


def load_config() -> Dict[str, Any]:
    with _LOCK:
        return _read_raw()


def list_persons() -> List[Dict[str, Any]]:
    return list(load_config().get("persons") or [])


def get_permission_override(username: str) -> Optional[List[str]]:
    """返回人员级模块权限覆盖；未设置时返回 None，表示沿用角色权限。"""
    key = str(username or "").strip()
    raw = (load_config().get("permissionOverrides") or {}).get(key)
    if raw is None:
        return None
    return [str(item).strip() for item in raw if str(item).strip()]


def effective_permissions(db, username: str, role: str) -> List[str]:
    override = get_permission_override(username)
    if override is not None:
        return override
    from . import models
    return [row.perm_code for row in db.query(models.RolePermission).filter_by(role_code=role).all()]


def assignable_permission_codes() -> set[str]:
    """人员可覆盖的权限：六个模块父权限 + 功能树中的已登记子权限。"""
    codes = set(MODULE_PARENT_PERMISSIONS)
    for module in function_tree_store.load_module_registry().get("modules", []):
        for child in function_tree_store._module_children(str(module.get("key") or "")):
            code = str(child.get("permission") or "").strip()
            if code:
                codes.add(code)
    return codes.intersection(permission_registry.registered_codes())


def normalize_override_permissions(permissions: List[str]) -> List[str]:
    codes = sorted({str(code).strip() for code in (permissions or []) if str(code).strip()})
    known = permission_registry.registered_codes()
    assignable = assignable_permission_codes()
    unknown = [code for code in codes if code not in known]
    if unknown:
        raise ValueError("未知权限：" + ", ".join(unknown))
    denied = [code for code in codes if code not in assignable]
    if denied:
        raise ValueError("不能设置该权限：" + ", ".join(denied))
    parent_by_child = {}
    for module in function_tree_store.load_module_registry().get("modules", []):
        parent = str(module.get("permission") or "").strip()
        for child in function_tree_store._module_children(str(module.get("key") or "")):
            child_code = str(child.get("permission") or "").strip()
            if child_code and parent:
                parent_by_child[child_code] = parent
    missing = sorted({parent_by_child[code] for code in codes if code in parent_by_child and parent_by_child[code] not in codes})
    if missing:
        raise ValueError("请先勾选模块权限：" + ", ".join(missing))
    return codes


def set_permission_override(username: str, permissions: List[str], db, actor: str) -> List[str]:
    key = str(username or "").strip()
    if not key:
        raise ValueError("用户名不能为空")
    codes = normalize_override_permissions(permissions)
    with _LOCK:
        config = _read_raw()
        config.setdefault("permissionOverrides", {})[key] = codes
        _write_raw(config)
    write_audit(db, actor, "person.permissions.update", key, "perms=" + ",".join(codes), commit=True)
    return codes


def get_person(username: str) -> Dict[str, Any] | None:
    key = (username or "").strip()
    return next((p for p in list_persons() if p.get("username") == key), None)


COORDINATED_MODULES = ("machine", "material", "method", "environment")
GRANT_ACTIONS = ("view", "operate", "manage")


def _validate_module_grants(value: Any) -> Dict[str, Dict[str, bool]]:
    raw = value if isinstance(value, dict) else {}
    result: Dict[str, Dict[str, bool]] = {}
    for key in COORDINATED_MODULES:
        item = raw.get(key) if isinstance(raw.get(key), dict) else {}
        result[key] = {action: bool(item.get(action, False)) for action in GRANT_ACTIONS}
    return result


def _validate_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
    username = str(payload.get("username") or "").strip()
    if not username:
        raise ValueError("用户名不能为空")
    return {
        "username": username[:64],
        "department": str(payload.get("department") or "")[:64],
        "position": str(payload.get("position") or "")[:64],
        "parentUsername": str(payload.get("parentUsername") or "").strip()[:64],
        "phone": str(payload.get("phone") or "")[:32],
        "status": str(payload.get("status") or "active")[:16],
        "moduleGrants": _validate_module_grants(payload.get("moduleGrants")),
        "relatedStations": relation_items.normalize_items(payload.get("relatedStations")),
        "relatedProducts": relation_items.normalize_items(payload.get("relatedProducts")),
        "relatedEquipment": relation_items.normalize_items(payload.get("relatedEquipment")),
        "notes": str(payload.get("notes") or "")[:500],
    }


def create_person(payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    meta = _validate_meta(payload)
    with _LOCK:
        config = _read_raw()
        persons = config.setdefault("persons", [])
        if any(p.get("username") == meta["username"] for p in persons):
            raise ValueError("人员记录已存在")
        now = _now()
        meta.update({"createdBy": actor, "createdAt": now, "updatedBy": actor, "updatedAt": now})
        persons.append(meta)
        _write_raw(config)
    write_audit(db, actor, "person.create", meta["username"], f"department={meta['department']}; position={meta['position']}", commit=True)
    return meta


def sync_name(username: str, name: str, actor: str) -> None:
    """仅同步账号姓名到人员扩展信息，不覆盖其他人员字段。"""
    with _LOCK:
        config = _read_raw()
        target = next((p for p in config.setdefault("persons", []) if p.get("username") == username), None)
        if target:
            target["name"] = name
            target["updatedBy"] = actor
            target["updatedAt"] = _now()
            _write_raw(config)


def rename_position(old_position: str, new_position: str, db: Session, actor: str) -> Dict[str, Any]:
    old = str(old_position or "").strip()
    new = str(new_position or "").strip()[:64]
    if not old:
        raise ValueError("原岗位不能为空")
    if not new:
        raise ValueError("新岗位不能为空")
    if old == new:
        return {"changed": 0, "from": old, "to": new}
    with _LOCK:
        config = _read_raw()
        persons = config.setdefault("persons", [])
        targets = [p for p in persons if str(p.get("position") or "") == old]
        if not targets:
            raise ValueError("岗位不存在：" + old)
        for target in targets:
            target["position"] = new
            target["updatedBy"] = actor
            target["updatedAt"] = _now()
        _write_raw(config)
        count = len(targets)
    write_audit(db, actor, "person.position.rename", new, f"from={old}; changed={count}", commit=True)
    return {"changed": count, "from": old, "to": new}


def update_person(payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    meta = _validate_meta(payload)
    with _LOCK:
        config = _read_raw()
        persons = config.setdefault("persons", [])
        target = next((p for p in persons if p.get("username") == meta["username"]), None)
        if not target:
            raise ValueError("人员记录不存在")
        target.update({
            "department": meta["department"], "position": meta["position"],
            "parentUsername": meta["parentUsername"], "phone": meta["phone"],
            "status": meta["status"], "moduleGrants": meta["moduleGrants"],
            "relatedStations": meta["relatedStations"], "relatedProducts": meta["relatedProducts"],
            "relatedEquipment": meta["relatedEquipment"],
            "notes": meta["notes"], "updatedBy": actor, "updatedAt": _now(),
        })
        _write_raw(config)
        result = dict(target)
    write_audit(db, actor, "person.update", meta["username"], f"department={meta['department']}; status={meta['status']}", commit=True)
    return result
