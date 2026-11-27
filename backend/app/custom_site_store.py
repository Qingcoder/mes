"""自定义站点与访问流程配置存储。

使用 JSON 文件持久化，避免新增数据库结构；写入采用临时文件 + os.replace 原子替换。
所有变更同时写入 audit_logs，便于查询和追溯。
"""
import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .permission_guard import write_audit

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "custom_sites.json")
_LOCK = threading.Lock()
VERSION = 1


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _default_config() -> Dict[str, Any]:
    now = _now()
    return {
        "version": VERSION,
        "updatedAt": now,
        "groups": [
            {"id": "grp_prod", "name": "生产作业", "description": "车间现场常用作业入口", "order": 1},
            {"id": "grp_sys", "name": "系统管理", "description": "权限与配置入口", "order": 2},
        ],
        "sites": [
            {
                "id": "site_station", "name": "站点作业", "url": "/station",
                "description": "扫码枪 / 手机扫码过站作业", "icon": "▷",
                "groupId": "grp_prod", "order": 1, "enabled": True,
                "access": {"roles": [], "users": []},
                "flow": {"mode": "sequence", "order": 1, "nextRule": "none", "nextSiteId": "", "jumpUrl": ""},
            },
            {
                "id": "site_pack", "name": "包装管理", "url": "/pack",
                "description": "成箱包装与出库管理", "icon": "▣",
                "groupId": "grp_prod", "order": 2, "enabled": True,
                "access": {"roles": [], "users": []},
                "flow": {"mode": "sequence", "order": 2, "nextRule": "none", "nextSiteId": "", "jumpUrl": ""},
            },
            {
                "id": "site_access", "name": "站点流程权限", "url": "/access-control",
                "description": "配置站点与流程访问权限", "icon": "◈",
                "groupId": "grp_sys", "order": 1, "enabled": True,
                "access": {"roles": ["admin"], "users": []},
                "flow": {"mode": "manual", "order": 1, "nextRule": "none", "nextSiteId": "", "jumpUrl": ""},
            },
        ],
        "flows": [
            {
                "id": "flow_prod", "name": "默认生产入口流程",
                "description": "按顺序展示生产作业入口",
                "siteIds": ["site_station", "site_pack"],
                "access": {"roles": [], "users": []},
                "enabled": True, "order": 1,
            },
        ],
    }


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
    config.setdefault("groups", [])
    config.setdefault("sites", [])
    config.setdefault("flows", [])
    config.setdefault("updatedAt", _now())
    return config


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def load_config() -> Dict[str, Any]:
    with _LOCK:
        return _read_raw()


def save_config(config: Dict[str, Any], db: Session, actor: str, action: str, target: str, detail: str) -> Dict[str, Any]:
    with _LOCK:
        _write_raw(config)
        write_audit(db, actor, action, target, detail[:512], commit=True)
    return config


def _new_id(prefix: str, items: List[Dict[str, Any]]) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL 不能为空")
    if url.startswith("/"):
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    raise ValueError("URL 必须以 /、http:// 或 https:// 开头")


def _access(value: Any) -> Dict[str, List[str]]:
    value = value or {}
    return {
        "roles": [str(x) for x in (value.get("roles") or []) if str(x).strip()],
        "users": [str(x) for x in (value.get("users") or []) if str(x).strip()],
    }


def _visible_to(access: Dict[str, Any], username: str, role: str) -> bool:
    access = _access(access)
    if not access["roles"] and not access["users"]:
        return True
    if username in access["users"]:
        return True
    return role in access["roles"]


def visible_config(config: Dict[str, Any], username: str, role: str, can_manage: bool) -> Dict[str, Any]:
    if can_manage:
        return config
    sites = [s for s in config.get("sites", []) if s.get("enabled", True) and _visible_to(s.get("access"), username, role)]
    site_ids = {s["id"] for s in sites}
    groups = [
        g for g in config.get("groups", [])
        if any(s.get("groupId") == g["id"] for s in sites)
    ]
    flows = [
        f for f in config.get("flows", [])
        if f.get("enabled", True) and _visible_to(f.get("access"), username, role)
        and any(sid in site_ids for sid in (f.get("siteIds") or []))
    ]
    return {**config, "groups": groups, "sites": sites, "flows": flows}


def create_site(payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    config = load_config()
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("站点名称不能为空")
    site = {
        "id": _new_id("site", config["sites"]),
        "name": name[:64],
        "url": _validate_url(payload.get("url")),
        "description": (payload.get("description") or "")[:256],
        "icon": (payload.get("icon") or "◇")[:8],
        "groupId": (payload.get("groupId") or "").strip(),
        "order": int(payload.get("order") or len(config["sites"]) + 1),
        "enabled": bool(payload.get("enabled", True)),
        "access": _access(payload.get("access")),
        "flow": {
            "mode": (payload.get("flow") or {}).get("mode") or "manual",
            "order": int((payload.get("flow") or {}).get("order") or 1),
            "nextRule": (payload.get("flow") or {}).get("nextRule") or "none",
            "nextSiteId": (payload.get("flow") or {}).get("nextSiteId") or "",
            "jumpUrl": (payload.get("flow") or {}).get("jumpUrl") or "",
        },
    }
    config["sites"].append(site)
    save_config(config, db, actor, "custom.site.create", site["id"], site["name"])
    return site


def update_site(site_id: str, payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    config = load_config()
    site = next((s for s in config["sites"] if s["id"] == site_id), None)
    if not site:
        raise ValueError("站点不存在")
    for key in ("name", "description", "icon", "groupId", "order", "enabled"):
        if key in payload:
            site[key] = payload[key]
    if "url" in payload:
        site["url"] = _validate_url(payload.get("url"))
    if "access" in payload:
        site["access"] = _access(payload.get("access"))
    if "flow" in payload:
        site["flow"] = {**site.get("flow", {}), **(payload.get("flow") or {})}
    if not site.get("name"):
        raise ValueError("站点名称不能为空")
    save_config(config, db, actor, "custom.site.update", site_id, site["name"])
    return site


def delete_site(site_id: str, db: Session, actor: str) -> bool:
    config = load_config()
    site = next((s for s in config["sites"] if s["id"] == site_id), None)
    if not site:
        raise ValueError("站点不存在")
    config["sites"] = [s for s in config["sites"] if s["id"] != site_id]
    for flow in config.get("flows", []):
        flow["siteIds"] = [sid for sid in (flow.get("siteIds") or []) if sid != site_id]
    save_config(config, db, actor, "custom.site.delete", site_id, site["name"])
    return True


def create_group(payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    config = load_config()
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("分组名称不能为空")
    group = {
        "id": _new_id("grp", config["groups"]), "name": name[:64],
        "description": (payload.get("description") or "")[:256],
        "order": int(payload.get("order") or len(config["groups"]) + 1),
    }
    config["groups"].append(group)
    save_config(config, db, actor, "custom.group.create", group["id"], group["name"])
    return group


def update_group(group_id: str, payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    config = load_config()
    group = next((g for g in config["groups"] if g["id"] == group_id), None)
    if not group:
        raise ValueError("分组不存在")
    for key in ("name", "description", "order"):
        if key in payload:
            group[key] = payload[key]
    save_config(config, db, actor, "custom.group.update", group_id, group["name"])
    return group


def delete_group(group_id: str, db: Session, actor: str) -> bool:
    config = load_config()
    group = next((g for g in config["groups"] if g["id"] == group_id), None)
    if not group:
        raise ValueError("分组不存在")
    config["groups"] = [g for g in config["groups"] if g["id"] != group_id]
    for site in config["sites"]:
        if site.get("groupId") == group_id:
            site["groupId"] = ""
    save_config(config, db, actor, "custom.group.delete", group_id, group["name"])
    return True


def create_flow(payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    config = load_config()
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("流程名称不能为空")
    flow = {
        "id": _new_id("flow", config["flows"]), "name": name[:64],
        "description": (payload.get("description") or "")[:256],
        "siteIds": [str(x) for x in (payload.get("siteIds") or [])],
        "access": _access(payload.get("access")),
        "enabled": bool(payload.get("enabled", True)),
        "order": int(payload.get("order") or len(config["flows"]) + 1),
    }
    config["flows"].append(flow)
    save_config(config, db, actor, "custom.flow.create", flow["id"], flow["name"])
    return flow


def update_flow(flow_id: str, payload: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    config = load_config()
    flow = next((f for f in config["flows"] if f["id"] == flow_id), None)
    if not flow:
        raise ValueError("流程不存在")
    for key in ("name", "description", "siteIds", "enabled", "order"):
        if key in payload:
            flow[key] = payload[key]
    if "access" in payload:
        flow["access"] = _access(payload.get("access"))
    save_config(config, db, actor, "custom.flow.update", flow_id, flow["name"])
    return flow


def delete_flow(flow_id: str, db: Session, actor: str) -> bool:
    config = load_config()
    flow = next((f for f in config["flows"] if f["id"] == flow_id), None)
    if not flow:
        raise ValueError("流程不存在")
    config["flows"] = [f for f in config["flows"] if f["id"] != flow_id]
    save_config(config, db, actor, "custom.flow.delete", flow_id, flow["name"])
    return True


def resolve_next(site_id: str, username: str, role: str, can_manage: bool) -> Optional[Dict[str, Any]]:
    config = visible_config(load_config(), username, role, can_manage)
    site = next((s for s in config["sites"] if s["id"] == site_id), None)
    if not site:
        return None
    flow_cfg = site.get("flow") or {}
    if flow_cfg.get("nextRule") == "url":
        return {"type": "url", "url": flow_cfg.get("jumpUrl") or ""}
    if flow_cfg.get("nextRule") == "site":
        next_id = flow_cfg.get("nextSiteId") or ""
        target = next((s for s in config["sites"] if s["id"] == next_id), None)
        if target:
            return {"type": "site", "url": target["url"], "name": target["name"]}
    if flow_cfg.get("nextRule") == "sequence":
        candidates = sorted(
            [s for s in config["sites"] if s.get("groupId") == site.get("groupId") and s.get("enabled", True)],
            key=lambda s: s.get("order", 0),
        )
        current = next((i for i, s in enumerate(candidates) if s["id"] == site_id), -1)
        if current >= 0 and current + 1 < len(candidates):
            target = candidates[current + 1]
            return {"type": "site", "url": target["url"], "name": target["name"]}
    return None
