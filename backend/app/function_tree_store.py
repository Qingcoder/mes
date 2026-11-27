"""统一功能树：功能、权限项、路由配置共用同一份数据源。"""
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from . import models
from .permission_guard import write_audit

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "function_tree.json")
ROUTE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_route_config.json")
TEMPLATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "role_templates.json")
MODULE_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "module_registry.json")
_LOCK = threading.Lock()
VERSION = 1
DEFAULT_FUNCTION_IDS = [
    "func_wo_view", "func_wo_create", "func_sn_import", "func_station_op",
    "func_rework_op", "func_pack_op", "func_query_view",
]


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _atomic_write(path: str, payload: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_tree() -> Dict[str, Any]:
    with _LOCK:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def load_route_config() -> Dict[str, Any]:
    if not os.path.exists(ROUTE_FILE):
        return {"version": VERSION, "updatedAt": "", "updatedBy": "", "functions": [], "permissions": [], "routes": []}
    with _LOCK:
        with open(ROUTE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def load_templates() -> Dict[str, Any]:
    if not os.path.exists(TEMPLATE_FILE):
        return {"version": VERSION, "items": []}
    with _LOCK:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def known_function_ids() -> set[str]:
    return {n.get("id") for n in _walk(load_tree().get("nodes", [])) if n.get("permission")}


def _walk(nodes: Iterable[Dict[str, Any]]):
    for node in nodes:
        yield node
        children = node.get("children") or []
        if children:
            yield from _walk(children)


def build_config(selected: List[str], actor: str) -> Dict[str, Any]:
    tree = load_tree()
    known = {n.get("id") for n in _walk(tree.get("nodes", [])) if n.get("permission")}
    unknown = [x for x in selected if x not in known]
    if unknown:
        raise ValueError("未知功能：" + ", ".join(unknown))

    selected_set = set(selected)
    permissions: Dict[str, Dict[str, str]] = {}
    routes: Dict[str, Dict[str, Any]] = {}
    functions: List[Dict[str, Any]] = []

    for node in _walk(tree.get("nodes", [])):
        if node.get("id") not in selected_set or not node.get("permission"):
            continue
        functions.append({
            "id": node.get("id"),
            "name": node.get("name", ""),
            "module": node.get("module", ""),
            "permission": node.get("permission", ""),
            "route": node.get("route", ""),
            "fixed": bool(node.get("fixed", False)),
            "description": node.get("description", ""),
        })
        code = node.get("permission", "")
        permissions.setdefault(code, {
            "code": code,
            "name": node.get("name") or code,
            "module": node.get("module") or "功能",
        })
        route = str(node.get("route") or "").strip()
        if route and route not in routes:
            routes[route] = {
                "path": route,
                "name": node.get("id", "").replace("func_", ""),
                "label": node.get("name", ""),
                "component": node.get("component", ""),
                "permission": code,
                "module": node.get("module", ""),
            }

    return {
        "version": VERSION,
        "updatedAt": _now(),
        "updatedBy": actor,
        "functions": functions,
        "permissions": list(permissions.values()),
        "routes": list(routes.values()),
    }


def apply_selected(selected: List[str], db: Session, actor: str) -> Dict[str, Any]:
    config = build_config(selected, actor)
    with _LOCK:
        _atomic_write(ROUTE_FILE, config)
        existing = {p.code: p for p in db.query(models.Permission).all()}
        for item in config["permissions"]:
            row = existing.get(item["code"])
            if row:
                row.name = item["name"]
                row.module = item["module"]
            else:
                db.add(models.Permission(
                    code=item["code"], name=item["name"], module=item["module"],
                ))
        write_audit(
            db, actor, "function.config.apply", "function_tree",
            f"functions={len(config['functions'])}; permissions={len(config['permissions'])}; routes={len(config['routes'])}",
            commit=False,
        )
    return config


def load_module_registry() -> Dict[str, Any]:
    with _LOCK:
        with open(MODULE_REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def _sorted_registry_modules() -> List[Dict[str, Any]]:
    return sorted(load_module_registry()["modules"], key=lambda x: int(x["order"]))


def _module_children(module_key: str) -> List[Dict[str, Any]]:
    children: List[Dict[str, Any]] = []
    for group in load_tree().get("nodes", []):
        for node in group.get("children", []):
            if node.get("moduleKey") != module_key or not node.get("permission"):
                continue
            children.append({
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "permission": node.get("permission", ""),
                "route": node.get("route", ""),
                "component": node.get("component", ""),
                "description": node.get("description", group.get("name", "")),
                "moduleKey": module_key,
            })
    return children


def combo_permission_order() -> List[str]:
    modules = _sorted_registry_modules()
    result: List[str] = []
    for module in modules:
        if module["permission"] not in result:
            result.append(module["permission"])
    for module in modules:
        for child in _module_children(module["key"]):
            if child["permission"] not in result:
                result.append(child["permission"])
    return result


def combo_function_order() -> List[str]:
    modules = _sorted_registry_modules()
    result: List[str] = []
    for module in modules:
        if module.get("functionId") and module["functionId"] not in result:
            result.append(module["functionId"])
    for module in modules:
        for child in _module_children(module["key"]):
            if child.get("id") and child["id"] not in result:
                result.append(child["id"])
    return result


def _function_index() -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for group in load_tree().get("nodes", []):
        for node in group.get("children", []):
            if node.get("id") and node.get("permission"):
                result[node["id"]] = node
    return result


def _effective_modules(module_keys: List[str], function_ids: List[str]) -> List[str]:
    modules = list(dict.fromkeys(module_keys or []))
    registry_keys = {m["key"] for m in _sorted_registry_modules()}
    known_functions = _function_index()
    unknown = [k for k in modules if k not in registry_keys]
    if unknown:
        raise ValueError("未知模块：" + ", ".join(unknown))
    for fid in function_ids or []:
        node = known_functions.get(fid)
        if not node:
            raise ValueError("未知子权限：" + fid)
        module_key = node.get("moduleKey")
        if module_key and module_key not in modules:
            modules.append(module_key)
    return modules


def combo_code(module_keys: List[str], function_ids: Optional[List[str]] = None) -> str:
    modules = _effective_modules(module_keys, function_ids or [])
    registry = {m["key"]: m for m in _sorted_registry_modules()}
    known_functions = _function_index()
    selected_function_ids = {
        *(registry[k].get("functionId") for k in modules if registry[k].get("functionId")),
        *(function_ids or []),
    }
    order = combo_function_order()
    mask = sum(1 << index for index, fid in enumerate(order) if fid in selected_function_ids)
    if not mask:
        raise ValueError("至少选择一个模块权限")
    return f"{load_module_registry().get('codePrefix', 'RB')}-{mask:03d}"


def combo_modules_by_permissions(permissions: List[str]) -> List[Dict[str, Any]]:
    selected = set(permissions or [])
    rows: List[Dict[str, Any]] = []
    for module in _sorted_registry_modules():
        children = _module_children(module["key"])
        child_selected = [c for c in children if c["permission"] in selected]
        if module["permission"] not in selected and not child_selected:
            continue
        rows.append({
            "key": module["key"], "name": module["name"], "order": int(module["order"]),
            "permission": module["permission"], "route": module.get("route", ""),
            "component": module.get("component", ""),
            "description": module.get("description", ""),
            "functionId": module.get("functionId", ""),
            "selected": True,
            "children": [{**c, "selected": c in child_selected} for c in children],
        })
    return rows


def combo_modules(module_keys: List[str], function_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    modules = set(_effective_modules(module_keys, function_ids or []))
    selected_functions = set(function_ids or [])
    return [
        {
            "key": m["key"], "name": m["name"], "order": int(m["order"]),
            "permission": m["permission"], "route": m.get("route", ""),
            "component": m.get("component", ""),
            "description": m.get("description", ""),
            "functionId": m.get("functionId", ""),
            "selected": m["key"] in modules,
            "children": [
                {**c, "selected": c["id"] in selected_functions}
                for c in _module_children(m["key"])
            ],
        }
        for m in _sorted_registry_modules()
    ]
