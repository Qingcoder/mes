"""权限目录与权限项数码的统一数据源。"""
import json
import os
import threading
from typing import Any, Dict, List

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "permission_registry.json")
_LOCK = threading.Lock()


def load() -> Dict[str, Any]:
    with _LOCK:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    codes = [p["code"] for p in config.get("permissions", [])]
    duplicates = sorted({c for c in codes if codes.count(c) > 1})
    if duplicates:
        raise ValueError("权限目录存在重复权限码：" + ", ".join(duplicates))
    return config


def permission_rows() -> List[Dict[str, str]]:
    return load().get("permissions", [])


def registered_codes() -> set[str]:
    return {p["code"] for p in permission_rows()}


def permission_combo_code(permissions) -> str:
    """按权限项数量生成 PM-xxx；顺序无关，未登记权限直接报错。"""
    values = list(dict.fromkeys(permissions or []))
    known = registered_codes()
    unknown = [p for p in values if p not in known]
    if unknown:
        raise ValueError("权限项数码包含未登记权限：" + ", ".join(unknown))
    return f"{load().get('codePrefix', 'PM')}-{len(values):03d}"
