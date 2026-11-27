"""人机料法环领域配置存储。

只负责保存用户编辑的模块结构，不生成真实路由、菜单或权限逻辑。
"""
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from .permission_guard import write_audit

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "domain_config.json")
_LOCK = threading.Lock()
VERSION = 1


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _default_config() -> Dict[str, Any]:
    return {
        "version": VERSION,
        "updatedAt": _now(),
        "updatedBy": "",
        "domains": [
            {
                "key": "dashboard",
                "name": "看板",
                "route": "",
                "menuGroup": "",
                "permission": "",
                "description": "展示工单、生产报工、设备状态、质量检验等关键指标的汇总视图。",
                "children": [],
                "relations": [],
                "notes": "",
            },
            {
                "key": "person",
                "name": "人员管理",
                "route": "",
                "menuGroup": "",
                "permission": "",
                "description": "维护员工档案、部门/产线/班组归属、岗位角色与系统账号，控制工单管理、生产报工、物料追溯、设备状态、质量检验等模块的访问权限。",
                "children": [],
                "relations": [],
                "notes": "",
            },
            {
                "key": "machine",
                "name": "设备管理",
                "route": "",
                "menuGroup": "",
                "permission": "",
                "description": "管理设备台账、运行/停机/维修状态、点检维护记录及设备使用环境，支撑生产报工与设备状态联动。",
                "children": [],
                "relations": [],
                "notes": "",
            },
            {
                "key": "material",
                "name": "物料管理",
                "route": "",
                "menuGroup": "",
                "permission": "",
                "description": "管理原材料、半成品、成品台账与批次追溯，关联工单领料、包装出库和材料环境/配置，支撑物料追溯。",
                "children": [],
                "relations": [],
                "notes": "",
            },
            {
                "key": "method",
                "name": "工艺管理",
                "route": "",
                "menuGroup": "",
                "permission": "",
                "description": "维护工艺流程、作业指导、站点顺序与不良代码规则，支撑过站报工、返修流转和工艺追溯。",
                "children": [],
                "relations": [],
                "notes": "",
            },
            {
                "key": "environment",
                "name": "环境配置",
                "route": "",
                "menuGroup": "",
                "permission": "",
                "description": "维护部门、产线、工位/站点、存储环境及软硬件配置，关联人员作业环境、设备使用环境、物料存放条件和工艺依赖。",
                "children": [],
                "relations": [],
                "notes": "",
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
    config.setdefault("domains", [])
    config.setdefault("updatedAt", _now())
    config.setdefault("updatedBy", "")
    return config


def load_config() -> Dict[str, Any]:
    with _LOCK:
        return _read_raw()


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def _validate_domains(domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(domains, list):
        raise ValueError("domains 必须是数组")
    if len(domains) != 5:
        raise ValueError("人机料法环必须保持 5 个领域")
    result: List[Dict[str, Any]] = []
    seen = set()
    for item in domains:
        if not isinstance(item, dict):
            raise ValueError("每个领域必须是对象")
        key = str(item.get("key") or "").strip()
        name = str(item.get("name") or "").strip()
        if not key:
            raise ValueError("每个领域必须填写 key")
        if not name:
            raise ValueError(f"领域 {key} 必须填写名称")
        if key in seen:
            raise ValueError(f"领域 key 重复：{key}")
        seen.add(key)
        # 保留用户填写的全部字段，只做基础类型与长度保护。
        cleaned = dict(item)
        cleaned["key"] = key
        cleaned["name"] = name[:20]
        for field in ("route", "menuGroup", "permission", "description", "notes"):
            if field in cleaned:
                cleaned[field] = str(cleaned[field] or "")[:500]
        result.append(cleaned)
    return result


def save_config(domains: List[Dict[str, Any]], db: Session, actor: str) -> Dict[str, Any]:
    cleaned = _validate_domains(domains)
    with _LOCK:
        config = _read_raw()
        config["domains"] = cleaned
        config["updatedBy"] = actor
        _write_raw(config)
        summary = ",".join(f"{d['key']}:{d.get('route') or '-'}" for d in cleaned)
        write_audit(db, actor, "domain.config.save", "five-domains", summary[:512], commit=True)
    return config
