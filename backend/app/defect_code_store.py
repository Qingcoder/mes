"""不良代码库。

按产品、工站、维修手段分类；同一分类同一名称复用同一编码。
使用独立 JSON 文件保存，不新增数据库表。
"""
import json
import os
import re
import threading
from datetime import datetime
from typing import Any, Dict, List

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "defect_codes.json")
_LOCK = threading.Lock()
VERSION = 1
REPAIR_METHODS = [
    {"code": "REPAIR", "name": "维修返修"},
    {"code": "ADJUST", "name": "调整校准"},
    {"code": "REPLACE", "name": "更换部件"},
    {"code": "CLEAN", "name": "清洁处理"},
    {"code": "SOFTWARE", "name": "软件处理"},
    {"code": "OTHER", "name": "其他"},
]
_METHOD_CODES = {item["name"]: item["code"] for item in REPAIR_METHODS}
_METHOD_CODES.update({item["code"]: item["code"] for item in REPAIR_METHODS})


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _default() -> Dict[str, Any]:
    return {"version": VERSION, "updatedAt": _now(), "items": []}


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
        return config
    config.setdefault("version", VERSION)
    config.setdefault("updatedAt", _now())
    config.setdefault("items", [])
    return config


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, DATA_FILE)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _method_code(method: str) -> str:
    name = _text(method)
    return _METHOD_CODES.get(name, "OTHER")


def _safe_part(value: str, fallback: str) -> str:
    part = re.sub(r"[^A-Za-z0-9]+", "", _text(value).upper())
    return part or fallback


def _key(row: Dict[str, Any]) -> tuple:
    return (
        _text(row.get("productCode")).upper(),
        _text(row.get("stationCode")).upper(),
        _method_code(row.get("repairMethod")),
        _text(row.get("name")).lower(),
    )


def list_codes(keyword: str = "", product_code: str = "", station_code: str = "", repair_method: str = "") -> List[Dict[str, Any]]:
    with _LOCK:
        rows = [dict(row) for row in _read_raw().get("items", [])]
    q = _text(keyword).lower()
    result = []
    for row in rows:
        if product_code and _text(row.get("productCode")).upper() != _text(product_code).upper():
            continue
        if station_code and _text(row.get("stationCode")).upper() != _text(station_code).upper():
            continue
        if repair_method and _method_code(row.get("repairMethod")) != _method_code(repair_method):
            continue
        if q and not q in " ".join(_text(row.get(field)) for field in ("code", "name", "productName", "stationName", "repairMethod", "description")).lower():
            continue
        result.append(row)
    return sorted(result, key=lambda row: (
        _text(row.get("productCode")), _text(row.get("stationCode")),
        _text(row.get("repairMethod")), _text(row.get("code")),
    ))


def get_code(code: str) -> Dict[str, Any]:
    target = _text(code).upper()
    for row in list_codes():
        if _text(row.get("code")).upper() == target:
            return row
    return {}


def _next_code(rows: List[Dict[str, Any]], product_code: str, station_code: str, repair_method: str) -> str:
    prefix = "NG-{}-{}-{}".format(
        _safe_part(product_code, "ALL"),
        _safe_part(station_code, "STA"),
        _method_code(repair_method),
    )
    used = {_text(row.get("code")).upper() for row in rows}
    index = 1
    while True:
        candidate = f"{prefix}-{index:03d}"
        if candidate not in used:
            return candidate
        index += 1


def create_code(payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    name = _text(payload.get("name"))
    if not name:
        raise ValueError("不良代码名称不能为空")
    with _LOCK:
        config = _read_raw()
        rows = config.setdefault("items", [])
        wanted = _key(payload)
        existing = next((row for row in rows if _key(row) == wanted), None)
        if existing:
            return dict(existing)
        product_code = _text(payload.get("productCode")).upper()
        station_code = _text(payload.get("stationCode")).upper()
        repair_method = _text(payload.get("repairMethod")) or "OTHER"
        if repair_method not in _METHOD_CODES:
            repair_method = next((item["name"] for item in REPAIR_METHODS if item["code"] == repair_method), "其他")
        row = {
            "id": f"defect_{len(rows) + 1:04d}",
            "code": _next_code(rows, product_code, station_code, repair_method),
            "name": name,
            "productCode": product_code,
            "productName": _text(payload.get("productName")),
            "stationCode": station_code,
            "stationName": _text(payload.get("stationName")),
            "repairMethod": repair_method,
            "description": _text(payload.get("description")),
            "enabled": True,
            "createdBy": actor,
            "createdAt": _now(),
            "updatedBy": actor,
            "updatedAt": _now(),
        }
        rows.append(row)
        _write_raw(config)
        return dict(row)


def update_code(code: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    target = _text(code).upper()
    with _LOCK:
        config = _read_raw()
        rows = config.setdefault("items", [])
        row = next((item for item in rows if _text(item.get("code")).upper() == target), None)
        if not row:
            raise ValueError("不良代码不存在")
        candidate = dict(row)
        for field in ("name", "productCode", "productName", "stationCode", "stationName", "repairMethod", "description"):
            if field in (payload or {}):
                candidate[field] = _text(payload.get(field))
        candidate["productCode"] = candidate["productCode"].upper()
        candidate["stationCode"] = candidate["stationCode"].upper()
        if not candidate.get("name"):
            raise ValueError("不良代码名称不能为空")
        duplicate = next((item for item in rows if item is not row and _key(item) == _key(candidate)), None)
        if duplicate:
            raise ValueError("同一分类下已有同名不良代码：" + _text(duplicate.get("code")))
        row.update(candidate)
        row["updatedBy"] = actor
        row["updatedAt"] = _now()
        _write_raw(config)
        return dict(row)


def delete_code(code: str) -> bool:
    target = _text(code).upper()
    with _LOCK:
        config = _read_raw()
        rows = config.setdefault("items", [])
        kept = [row for row in rows if _text(row.get("code")).upper() != target]
        if len(kept) == len(rows):
            return False
        config["items"] = kept
        _write_raw(config)
        return True


def import_rows(rows: List[Dict[str, Any]], actor: str) -> Dict[str, Any]:
    created = 0
    reused = 0
    failed: List[Dict[str, Any]] = []
    for index, row in enumerate(rows or [], start=1):
        try:
            before = len(list_codes())
            create_code(row, actor)
            if len(list_codes()) > before:
                created += 1
            else:
                reused += 1
        except (TypeError, ValueError) as exc:
            failed.append({"row": index, "reason": str(exc)})
    return {"created": created, "reused": reused, "failed": failed}


def normalize_fail_codes(fail_codes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """工艺站点保存时只接受代码库中的不良代码，并带上分类信息。"""
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in fail_codes or []:
        code = _text(item.get("code")).upper()
        if not code:
            continue
        if code in seen:
            continue
        row = get_code(code)
        if not row:
            raise ValueError("不良代码不在代码库中：" + code)
        seen.add(code)
        result.append({
            "code": code,
            "name": _text(row.get("name")) or code,
            "productCode": _text(row.get("productCode")),
            "productName": _text(row.get("productName")),
            "stationCode": _text(row.get("stationCode")),
            "stationName": _text(row.get("stationName")),
            "repairMethod": _text(row.get("repairMethod")),
            "description": _text(row.get("description")),
        })
    return result


def template_csv() -> str:
    lines = [
        "产品编码,产品名称,工站编码,工站名称,维修手段,不良名称,说明",
        "P0001,V2.5无本体数采夹爪,OP10,夹爪测试,更换部件,示例：夹爪松动,来料松动；导入前请删除本行",
    ]
    return "\ufeff" + "\n".join(lines) + "\n"
