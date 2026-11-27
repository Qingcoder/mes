"""通用模块骨架存储。

仅提供机/料/法/环的占位记录 CRUD，不承载业务规则、状态机或校验逻辑。
人员模块已有独立实现，不走此存储。
"""
import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "module_skeleton.json")
_LOCK = threading.Lock()
VERSION = 1

MODULE_META: Dict[str, Dict[str, Any]] = {
    "dashboard": {"key": "dashboard", "name": "看板", "description": "生产关键指标汇总看板", "mode": "skeleton", "fields": ["指标名称", "当前值", "状态"]},
    "machine": {"key": "machine", "name": "设备管理", "description": "设备台账、运行/停机/维修状态与点检维护记录管理模块", "mode": "skeleton", "fields": ["设备编号", "设备名称", "运行状态"]},
    "material": {"key": "material", "name": "物料管理", "description": "原材料/半成品/成品台账、批次追溯与工单领料管理模块", "mode": "skeleton", "fields": ["物料编码", "物料名称", "批次"]},
    "method": {"key": "method", "name": "工艺管理", "description": "工艺流程、作业指导、站点顺序与不良代码规则管理模块", "mode": "skeleton", "fields": ["流程编码", "流程名称", "站点顺序"]},
    "environment": {"key": "environment", "name": "环境配置", "description": "部门、产线、工位/站点、存储环境与软硬件配置管理模块", "mode": "skeleton", "fields": ["配置编码", "配置名称", "适用对象"]},
    "person": {"key": "person", "name": "人员管理", "description": "员工档案、岗位角色、系统账号与生产模块权限管理模块", "mode": "dedicated", "api": "/api/persons", "fields": []},
}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _default() -> Dict[str, Any]:
    return {
        "version": VERSION,
        "updatedAt": _now(),
        "records": {key: [] for key in MODULE_META if MODULE_META[key]["mode"] == "skeleton"},
    }


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def _read_raw() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        config = _default()
        _write_raw(config)
        return config
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = _default()
        _write_raw(config)
    config.setdefault("version", VERSION)
    config.setdefault("records", {})
    config.setdefault("updatedAt", _now())
    for key in MODULE_META:
        if MODULE_META[key]["mode"] == "skeleton":
            config["records"].setdefault(key, [])
    return config


def meta_of(key: str) -> Dict[str, Any] | None:
    return MODULE_META.get(key)


def list_modules() -> List[Dict[str, Any]]:
    return list(MODULE_META.values())


def list_records(key: str) -> List[Dict[str, Any]]:
    with _LOCK:
        config = _read_raw()
        return list(config["records"].get(key, []))


def create_record(key: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    now = _now()
    record = {
        "id": f"{key}_{uuid.uuid4().hex[:10]}",
        "data": dict(payload or {}),
        "createdBy": actor,
        "createdAt": now,
        "updatedBy": actor,
        "updatedAt": now,
    }
    with _LOCK:
        config = _read_raw()
        config["records"].setdefault(key, []).append(record)
        _write_raw(config)
    return record


def update_record(key: str, record_id: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    with _LOCK:
        config = _read_raw()
        target = next((r for r in config["records"].get(key, []) if r.get("id") == record_id), None)
        if not target:
            raise ValueError("骨架记录不存在")
        target["data"] = dict(payload or {})
        target["updatedBy"] = actor
        target["updatedAt"] = _now()
        _write_raw(config)
        return dict(target)


def delete_record(key: str, record_id: str) -> bool:
    with _LOCK:
        config = _read_raw()
        records = config["records"].get(key, [])
        target = next((r for r in records if r.get("id") == record_id), None)
        if not target:
            raise ValueError("骨架记录不存在")
        records.remove(target)
        _write_raw(config)
    return True
