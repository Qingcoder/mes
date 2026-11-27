"""设备管理数据层。

独立保存设备台账与点检维护记录，采用临时文件 + os.replace 原子写入。
不复用 module_skeleton.json，避免占位记录与真实设备数据混在一起。
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import relation_items

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "equipment.json")
_LOCK = threading.Lock()
VERSION = 1

STATUS_ALIASES = {
    "running": "running", "运行": "running", "运行中": "running", "在用": "running",
    "idle": "idle", "空闲": "idle", "待机": "idle",
    "stopped": "stopped", "停机": "stopped", "停用": "stopped",
    "maintenance": "maintenance", "维修": "maintenance", "维修中": "maintenance", "保养": "maintenance", "维护": "maintenance",
    "scrapped": "scrapped", "报废": "scrapped",
}
STATUS_LABELS = {
    "running": "运行", "idle": "空闲", "stopped": "停机",
    "maintenance": "维修", "scrapped": "报废",
}
MAINTENANCE_TYPES = {"点检", "保养", "维修", "校准"}
MAINTENANCE_RESULTS = {"正常", "异常", "待处理", "已完成"}
CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _default_config() -> Dict[str, Any]:
    return {"version": VERSION, "updatedAt": _now(), "devices": []}


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
    config.setdefault("updatedAt", _now())
    config.setdefault("devices", [])
    return config


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, DATA_FILE)


def _text(value: Any, field: str, required: bool = False, limit: int = 200) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(field + "不能为空")
    if len(text) > limit:
        raise ValueError(field + "不能超过 " + str(limit) + " 字符")
    return text


def _date(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not DATE_RE.fullmatch(text):
        raise ValueError(field + "需使用 YYYY-MM-DD 格式")
    return text


def _status(value: Any) -> str:
    key = str(value or "").strip().lower()
    result = STATUS_ALIASES.get(key) or STATUS_ALIASES.get(str(value or "").strip())
    if not result:
        raise ValueError("设备状态不合法：" + str(value or ""))
    return result


def status_label(value: str) -> str:
    return STATUS_LABELS.get(str(value or ""), str(value or ""))


def _code(value: Any, field: str = "设备编号") -> str:
    code = str(value or "").strip().upper()
    if not CODE_RE.fullmatch(code):
        raise ValueError(field + "需以大写字母或数字开头，仅含 2-64 位大写字母、数字、下划线或短横线")
    return code


def list_devices(q: str = "", status: str = "", category: str = "") -> List[Dict[str, Any]]:
    needle = str(q or "").strip().lower()
    rows: List[Dict[str, Any]] = []
    for row in _read_raw().get("devices", []):
        if status and str(row.get("status", "")) != status:
            continue
        if category and str(row.get("category", "")) != category:
            continue
        if needle and needle not in " ".join([
            str(row.get("code", "")), str(row.get("name", "")), str(row.get("model", "")),
            str(row.get("brand", "")), str(row.get("serialNo", "")), str(row.get("location", "")),
            str(row.get("stationCode", "")), str(row.get("productCode", "")),
            str(row.get("productName", "")), str(row.get("operator", "")),
        ]).lower():
            continue
        rows.append(row)
    return sorted(rows, key=lambda r: str(r.get("code", "")))


def find_device(code_or_id: str) -> Optional[Dict[str, Any]]:
    key = str(code_or_id or "").strip().upper()
    return next((d for d in _read_raw().get("devices", [])
                 if str(d.get("code", "")).upper() == key or str(d.get("id", "")) == code_or_id), None)


def _normalize_device(payload: Dict[str, Any], existing_code: str = "", actor: str = "", now: str = "") -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("设备资料必须是对象")
    code = _code(payload.get("code") or existing_code)
    if existing_code and code != existing_code:
        raise ValueError("设备编号不允许修改")
    device = {
        "id": str(payload.get("id") or ("eq_" + uuid.uuid4().hex[:12])),
        "code": code,
        "stationName": _text(payload.get("stationName"), "关联工站名称", limit=128),
        "name": _text(payload.get("name"), "设备名称", True, 128),
        "model": _text(payload.get("model"), "设备型号", limit=128),
        "brand": _text(payload.get("brand"), "品牌", limit=128),
        "serialNo": _text(payload.get("serialNo"), "出厂序列号", limit=128).upper(),
        "category": _text(payload.get("category"), "设备类别", limit=64),
        "location": _text(payload.get("location"), "安装位置", limit=128),
        "department": _text(payload.get("department"), "所属部门", limit=128),
        "stationCode": _text(payload.get("stationCode"), "关联站点", limit=64).upper(),
        "productCode": _text(payload.get("productCode"), "关联产品", limit=64).upper(),
        "productName": _text(payload.get("productName"), "关联产品名称", limit=128),
        "relatedStations": relation_items.normalize_items(payload.get("relatedStations")),
        "relatedProducts": relation_items.normalize_items(payload.get("relatedProducts")),
        "relatedPersons": relation_items.normalize_items(payload.get("relatedPersons")),
        "status": _status(payload.get("status") or "idle"),
        "operator": _text(payload.get("operator"), "责任人", limit=64),
        "phone": _text(payload.get("phone"), "联系电话", limit=64),
        "purchaseDate": _date(payload.get("purchaseDate"), "购置日期"),
        "warrantyDate": _date(payload.get("warrantyDate"), "保修到期"),
        "remark": _text(payload.get("remark"), "备注", limit=500),
        "maintenance": payload.get("maintenance") or [],
        "createdBy": str(payload.get("createdBy") or actor or ""),
        "createdAt": str(payload.get("createdAt") or now or _now()),
        "updatedBy": actor or "",
        "updatedAt": now or _now(),
    }
    if not isinstance(device["maintenance"], list):
        raise ValueError("点检维护记录必须是数组")
    normalized = []
    for record in device["maintenance"]:
        normalized.append(_normalize_maintenance(record, actor=actor, now=now))
    device["maintenance"] = normalized
    return device


def _normalize_maintenance(payload: Dict[str, Any], actor: str = "", now: str = "") -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("点检维护记录必须是对象")
    mtype = _text(payload.get("type"), "记录类型", True, 32)
    if mtype not in MAINTENANCE_TYPES:
        raise ValueError("记录类型只能是：" + "、".join(sorted(MAINTENANCE_TYPES)))
    result = _text(payload.get("result"), "处理结果", limit=32) or "已完成"
    if result not in MAINTENANCE_RESULTS:
        raise ValueError("处理结果只能是：" + "、".join(sorted(MAINTENANCE_RESULTS)))
    return {
        "id": str(payload.get("id") or ("mnt_" + uuid.uuid4().hex[:12])),
        "date": _date(payload.get("date") or (now or _now())[:10], "日期"),
        "type": mtype,
        "content": _text(payload.get("content"), "内容", True, 500),
        "operator": _text(payload.get("operator"), "执行人", limit=64),
        "result": result,
        "nextDate": _date(payload.get("nextDate"), "下次日期"),
        "createdBy": str(payload.get("createdBy") or actor or ""),
        "createdAt": str(payload.get("createdAt") or now or _now()),
    }


def _next_auto_code(devices: List[Dict[str, Any]]) -> str:
    numbers = []
    for row in devices:
        match = re.fullmatch(r"EQ(\d+)", str(row.get("code", "")).strip().upper())
        if match:
            numbers.append(int(match.group(1)))
    index = 1
    while index in numbers:
        index += 1
    return f"EQ{index:04d}"


def _reference_aliases(code: Any, label: Any) -> List[str]:
    values = [str(code or "").strip(), str(label or "").strip()]
    for text in list(values):
        values.extend(re.split(r"[\s\-_/（）()·、,，]+", text))
    return sorted({v for v in values if len(v) >= 2}, key=len, reverse=True)


def _match_reference(name: str, candidates: List[tuple]) -> tuple:
    text = str(name or "").strip().lower()
    if not text:
        return "", ""
    best = ("", "", 0)
    for code, label in candidates:
        for key in _reference_aliases(code, label):
            key = key.lower()
            if key in text and len(key) > best[2]:
                best = (str(code or ""), str(label or ""), len(key))
    return best[0], best[1]


def auto_enrich(payload: Dict[str, Any], devices: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """按设备名称补足编号、默认状态和工站/产品关联，不覆盖已有显式字段。"""
    result = dict(payload or {})
    name = _text(result.get("name"), "设备名称", True, 128)
    result["name"] = name
    if not str(result.get("code") or "").strip():
        result["code"] = _next_auto_code(devices or [])
    result.setdefault("status", "idle")
    result.setdefault("category", "生产设备")
    from . import process_design_store, product_profiles_store
    if not str(result.get("stationCode") or "").strip():
        stations = []
        for station in process_design_store.load_config().get("stations", []):
            stations.append((station.get("code") or station.get("id") or "", station.get("name") or ""))
        station_code, station_name = _match_reference(name, stations)
        if station_code:
            result["stationCode"] = station_code
        if station_name:
            result["stationName"] = station_name
    if not str(result.get("productCode") or "").strip():
        products = []
        for product in product_profiles_store.list_profiles():
            products.append((product.get("code") or "", product.get("name") or product.get("family") or ""))
        product_code, product_name = _match_reference(name, products)
        if product_code:
            result["productCode"] = product_code
        if product_name:
            result["productName"] = product_name
    return result


def _ensure_unique(config: Dict[str, Any], code: str, serial: str = "", skip_id: str = "") -> None:
    for row in config.get("devices", []):
        if str(row.get("id")) == skip_id:
            continue
        if str(row.get("code", "")).upper() == code:
            raise ValueError("设备编号已存在：" + code)
        if serial and str(row.get("serialNo", "")).upper() == serial:
            raise ValueError("出厂序列号已存在：" + serial)


def create_device(payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    with _LOCK:
        config = _read_raw()
        now = _now()
        enriched = auto_enrich(payload, config.get("devices", []))
        device = _normalize_device(enriched, actor=actor, now=now)
        _ensure_unique(config, device["code"], device["serialNo"])
        config.setdefault("devices", []).append(device)
        _write_raw(config)
        return dict(device)


def update_device(code: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    code = _code(code)
    with _LOCK:
        config = _read_raw()
        index = next((i for i, d in enumerate(config.get("devices", []))
                      if str(d.get("code", "")).upper() == code), -1)
        if index < 0:
            raise ValueError("设备不存在")
        now = _now()
        merged = dict(config["devices"][index])
        merged.update(payload or {})
        if payload and str(payload.get("name") or "").strip() != str(config["devices"][index].get("name") or "").strip():
            for key in ("stationCode", "stationName", "productCode", "productName"):
                if key not in payload:
                    merged.pop(key, None)
            merged = auto_enrich(merged, config.get("devices", []))
        device = _normalize_device(merged, existing_code=code, actor=actor, now=now)
        _ensure_unique(config, device["code"], device["serialNo"], skip_id=device["id"])
        config["devices"][index] = device
        _write_raw(config)
        return dict(device)


def delete_device(code: str) -> bool:
    code = _code(code)
    with _LOCK:
        config = _read_raw()
        before = len(config.get("devices", []))
        config["devices"] = [d for d in config.get("devices", []) if str(d.get("code", "")).upper() != code]
        _write_raw(config)
        return len(config["devices"]) < before


def import_devices(rows: List[Any], actor: str) -> Dict[str, Any]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("导入数据不能为空")
    if len(rows) > 1000:
        raise ValueError("单次最多导入 1000 台设备")
    created: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    with _LOCK:
        config = _read_raw()
        now = _now()
        for index, raw in enumerate(rows, start=2):
            source = dict(raw) if isinstance(raw, dict) else {}
            code = str(source.get("code") or "").strip().upper()
            try:
                source = auto_enrich(source, config.get("devices", []) + created)
                device = _normalize_device(source, actor=actor, now=now)
                _ensure_unique(config, device["code"], device["serialNo"])
                if any(str(d.get("code", "")).upper() == device["code"] for d in created):
                    raise ValueError("本次文件中编码重复")
                config.setdefault("devices", []).append(device)
                created.append(dict(device))
            except ValueError as exc:
                skipped.append({"row": str(index), "code": code, "reason": str(exc)})
        _write_raw(config)
    return {"created": created, "skipped": skipped, "createdCount": len(created), "skippedCount": len(skipped)}


def _find_mutable_device(config: Dict[str, Any], code: str) -> Dict[str, Any]:
    key = _code(code)
    device = next((d for d in config.get("devices", []) if str(d.get("code", "")).upper() == key), None)
    if not device:
        raise ValueError("设备不存在")
    return device


def add_maintenance(code: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    code = _code(code)
    with _LOCK:
        config = _read_raw()
        device = _find_mutable_device(config, code)
        record = _normalize_maintenance(payload, actor=actor)
        device.setdefault("maintenance", []).append(record)
        device["updatedBy"] = actor
        device["updatedAt"] = _now()
        _write_raw(config)
        return record


def update_maintenance(code: str, record_id: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    code = _code(code)
    with _LOCK:
        config = _read_raw()
        device = _find_mutable_device(config, code)
        index = next((i for i, r in enumerate(device.get("maintenance", [])) if str(r.get("id")) == record_id), -1)
        if index < 0:
            raise ValueError("维护记录不存在")
        merged = dict(device["maintenance"][index])
        merged.update(payload or {})
        record = _normalize_maintenance(merged, actor=actor)
        record["id"] = record_id
        device["maintenance"][index] = record
        device["updatedBy"] = actor
        device["updatedAt"] = _now()
        _write_raw(config)
        return record


def delete_maintenance(code: str, record_id: str, actor: str) -> bool:
    code = _code(code)
    with _LOCK:
        config = _read_raw()
        device = _find_mutable_device(config, code)
        before = len(device.get("maintenance", []))
        device["maintenance"] = [r for r in device.get("maintenance", []) if str(r.get("id")) != record_id]
        if len(device["maintenance"]) == before:
            raise ValueError("维护记录不存在")
        device["updatedBy"] = actor
        device["updatedAt"] = _now()
        _write_raw(config)
        return True


def status_counts() -> Dict[str, int]:
    counts = {key: 0 for key in STATUS_LABELS}
    for device in _read_raw().get("devices", []):
        key = str(device.get("status", ""))
        if key in counts:
            counts[key] += 1
    return counts
