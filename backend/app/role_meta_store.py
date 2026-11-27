"""角色展示信息存储。

不新增数据库表；角色头像等展示字段按角色编码持久化。
"""
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "role_meta.json")
_LOCK = threading.Lock()
VERSION = 1


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _read_raw() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        config = {"version": VERSION, "updatedAt": _now(), "items": {}}
        _write_raw(config)
        return config
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = {"version": VERSION, "updatedAt": _now(), "items": {}}
        _write_raw(config)
    config.setdefault("version", VERSION)
    config.setdefault("items", {})
    config.setdefault("updatedAt", _now())
    return config


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def get_avatar(code: str) -> str:
    with _LOCK:
        return str((_read_raw().get("items") or {}).get(code, {}).get("avatar") or "")


def is_deleted(code: str) -> bool:
    with _LOCK:
        return bool((_read_raw().get("items") or {}).get(code, {}).get("deleted"))


def archive_deleted_role(code: str, snapshot: Dict[str, Any], actor: str) -> None:
    with _LOCK:
        config = _read_raw()
        row = config.setdefault("items", {}).setdefault(code, {})
        row["deleted"] = True
        row["deletedAt"] = _now()
        row["deletedBy"] = actor
        row["deletedSnapshot"] = dict(snapshot or {})
        row["updatedBy"] = actor
        row["updatedAt"] = _now()
        _write_raw(config)


def get_deleted_snapshot(code: str) -> Dict[str, Any]:
    with _LOCK:
        return dict((_read_raw().get("items") or {}).get(code, {}).get("deletedSnapshot") or {})


def restore_deleted_role(code: str, actor: str) -> None:
    with _LOCK:
        config = _read_raw()
        row = config.setdefault("items", {}).setdefault(code, {})
        row["deleted"] = False
        row["restoredAt"] = _now()
        row["restoredBy"] = actor
        row.pop("deletedAt", None)
        row.pop("deletedBy", None)
        row["updatedBy"] = actor
        row["updatedAt"] = _now()
        _write_raw(config)


def get_account_type(code: str) -> str:
    with _LOCK:
        return str((_read_raw().get("items") or {}).get(code, {}).get("accountType") or "")


def set_account_type(code: str, account_type: str, actor: str) -> str:
    value = str(account_type or "").strip()[:32]
    with _LOCK:
        config = _read_raw()
        items = config.setdefault("items", {})
        row = items.setdefault(code, {})
        row["accountType"] = value
        row["updatedBy"] = actor
        row["updatedAt"] = _now()
        _write_raw(config)
    return value


def get_combination(code: str) -> Dict[str, Any]:
    with _LOCK:
        return dict((_read_raw().get("items") or {}).get(code, {}).get("combination") or {})


def set_combination(code: str, combination: Dict[str, Any], actor: str) -> Dict[str, Any]:
    value = dict(combination or {})
    with _LOCK:
        config = _read_raw()
        items = config.setdefault("items", {})
        row = items.setdefault(code, {})
        row["combination"] = value
        row["updatedBy"] = actor
        row["updatedAt"] = _now()
        _write_raw(config)
    return value


def set_avatar(code: str, avatar: str, actor: str) -> str:
    value = str(avatar or "").strip()[:8]
    with _LOCK:
        config = _read_raw()
        items = config.setdefault("items", {})
        row = items.setdefault(code, {})
        row["avatar"] = value
        row["updatedBy"] = actor
        row["updatedAt"] = _now()
        _write_raw(config)
    return value
