"""工艺站点设计存储。

使用独立 JSON 文件保存站点布局、参数、数据关联和可视化配置；
不新增数据库表，不改变 /station 过站执行配置。写入采用临时文件 + os.replace 原子替换。
"""
import copy
import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from .permission_guard import write_audit
from .station_route_config import get_station_route_config

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "process_design.json")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "process_design")
MAX_PARAM_FILE_SIZE = 200 * 1024 * 1024
_LOCK = threading.Lock()
VERSION = 1
DEFAULT_STATION_TYPES = [
    {"value": "quality", "label": "质量"},
    {"value": "repair", "label": "维修"},
    {"value": "warehouse", "label": "包装/仓库"},
]
LEGACY_STATION_TYPES = {
    "normal": "quality", "test": "quality", "qc": "quality",
    "repair": "repair", "pack": "warehouse",
}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _default_library(flow: List[str], repair_code: str) -> List[Dict[str, Any]]:
    def items(prefix: str, count: int, start: int, step: int, item_type: str, label: str) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"lib_{prefix.lower()}_{start + index * step}",
                "code": f"{prefix}{start + index * step}",
                "name": f"{label}{start + index * step}",
                "type": item_type,
                "description": "",
            }
            for index in range(count)
        ]

    main_items = items("OP", max(8, len(flow) + 6), 10, 10, "quality", "主线站点")
    return [
        {
            "id": "lib_grp_flow", "name": "主线流程", "prefix": "OP", "start": 10, "step": 10,
            "description": "常规生产主线站点，编码 OP10、OP20、OP30 递增",
            "order": 1, "items": main_items,
        },
        {
            "id": "lib_grp_test", "name": "测试/检验", "prefix": "QC", "start": 10, "step": 10,
            "description": "测试与质量检验站点",
            "order": 2, "items": items("QC", 6, 10, 10, "quality", "检验站"),
        },
        {
            "id": "lib_grp_repair", "name": "维修返修", "prefix": "R", "start": 100, "step": 1,
            "description": "返修与回站处理站点",
            "order": 3, "items": items("R", 8, 100, 1, "repair", "维修站"),
        },
        {
            "id": "lib_grp_pack", "name": "包装出库", "prefix": "PK", "start": 10, "step": 10,
            "description": "装箱、包装与出库站点",
            "order": 4, "items": items("PK", 6, 10, 10, "warehouse", "包装站"),
        },
    ]


def _default_config() -> Dict[str, Any]:
    route = get_station_route_config("/station") or {}
    flow = [str(x) for x in route.get("flowStations", [])]
    repair = route.get("repairStation") or {}
    stations: List[Dict[str, Any]] = []
    for index, code in enumerate(flow, start=1):
        stations.append({
            "id": f"station_{code.lower()}",
            "code": code,
            "name": code,
            "type": "quality",
            "groupId": "grp_main_flow",
            "order": index,
            "enabled": True,
            "description": "",
            "workInstruction": "",
            "params": [],
            "paramFiles": [],
            "failCodes": [],
            "relatedProducts": [],
            "relatedEquipment": [],
            "relatedPersons": [],
            "returnStationId": "",
        })
    repair_code = str(repair.get("id", ""))
    if repair_code:
        stations.append({
            "id": f"station_{repair_code.lower()}",
            "code": repair_code,
            "name": str(repair.get("name") or repair_code),
            "type": "repair",
            "groupId": "grp_repair",
            "order": len(stations) + 1,
            "enabled": True,
            "description": "",
            "workInstruction": "",
            "params": [],
            "paramFiles": [],
            "failCodes": [],
            "relatedProducts": [],
            "relatedEquipment": [],
            "relatedPersons": [],
            "returnStationId": str(repair.get("returnStation") or ""),
        })
    return {
        "version": VERSION,
        "updatedAt": _now(),
        "groups": [
            {"id": "grp_main_flow", "name": "主线流程", "description": "产品正常流转的工艺站点", "order": 1},
            {"id": "grp_repair", "name": "维修处理", "description": "不良品维修与回站处理", "order": 2},
        ],
        "stations": stations,
        "library": _default_library(flow, repair_code),
        "settings": {
            "assignPolicy": route.get("assignPolicy", "first"),
            "snPoolScope": route.get("snPoolScope", "workOrder"),
            "failCodeScope": route.get("failCodeScope", "station"),
            "repairStationId": f"station_{repair_code.lower()}" if repair_code else "",
        },
        "options": {
            "libraryName": "工位/站点主数据",
            "stationTypes": [dict(item) for item in DEFAULT_STATION_TYPES],
        },
    }


def _migrate_station_types(config: Dict[str, Any]) -> bool:
    changed = False
    options = config.setdefault("options", {})
    raw_types = options.get("stationTypes") or []
    migrated_types: List[Dict[str, str]] = []
    seen_values: set[str] = set()
    for item in raw_types:
        if not isinstance(item, dict):
            changed = True
            continue
        raw_value = str(item.get("value", "")).strip().lower()
        mapped_value = LEGACY_STATION_TYPES.get(raw_value, raw_value)
        if not mapped_value or mapped_value in seen_values:
            changed = True
            continue
        default_item = next((d for d in DEFAULT_STATION_TYPES if d["value"] == mapped_value), None)
        label = default_item["label"] if raw_value in LEGACY_STATION_TYPES and default_item else str(item.get("label") or mapped_value)
        if mapped_value != raw_value or label != str(item.get("label") or ""):
            changed = True
        migrated_types.append({"value": mapped_value, "label": label})
        seen_values.add(mapped_value)
    for default_item in DEFAULT_STATION_TYPES:
        if default_item["value"] not in seen_values:
            migrated_types.append(dict(default_item))
            seen_values.add(default_item["value"])
            changed = True
    if changed:
        options["stationTypes"] = migrated_types
    for item in config.get("stations", []):
        old = str(item.get("type", ""))
        new = LEGACY_STATION_TYPES.get(old)
        if new and new != old:
            item["type"] = new
            changed = True
    for group in config.get("library", []):
        for item in group.get("items", []):
            old = str(item.get("type", ""))
            new = LEGACY_STATION_TYPES.get(old)
            if new and new != old:
                item["type"] = new
                changed = True
    return changed


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
    config.setdefault("groups", [])
    config.setdefault("stations", [])
    config.setdefault("library", _default_config()["library"])
    config.setdefault("settings", {})
    config.setdefault("options", _default_config()["options"])
    if _migrate_station_types(config):
        _write_raw(config)
    return config


def param_file_meta(station_id: str, filename: str, content_type: str, size: int) -> Dict[str, Any]:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(station_id or ""))[:64]
    if not safe_id:
        raise ValueError("站点 ID 不合法")
    filename = os.path.basename(str(filename or "未命名附件"))[:180] or "未命名附件"
    ext = os.path.splitext(filename)[1].lower()
    ext = re.sub(r"[^.a-z0-9]", "", ext)[:16]
    if not ext or ext == ".":
        ext = ".bin"
    if size <= 0 or size > MAX_PARAM_FILE_SIZE:
        raise ValueError("文件不能为空且不能超过 200MB")
    file_id = uuid.uuid4().hex
    return {
        "id": file_id,
        "stationId": safe_id,
        "name": filename,
        "extension": ext,
        "contentType": str(content_type or "application/octet-stream")[:120],
        "size": int(size),
        "parseable": False,
        "uploadedAt": _now(),
        "path": f"{safe_id}/{file_id}{ext}",
    }


def save_param_file(meta: Dict[str, Any], content: bytes) -> Dict[str, Any]:
    target = os.path.join(UPLOAD_DIR, str(meta["path"]))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "wb") as f:
        f.write(content)
    os.replace(tmp, target)
    return meta


def delete_param_file(station_id: str, file_id: str) -> bool:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(station_id or ""))[:64]
    safe_file = re.sub(r"[^A-Za-z0-9_-]", "", str(file_id or ""))
    if not safe_id or not safe_file:
        return False
    folder = os.path.join(UPLOAD_DIR, safe_id)
    if not os.path.isdir(folder):
        return False
    found = False
    for name in os.listdir(folder):
        if name.split(".", 1)[0] == safe_file:
            os.remove(os.path.join(folder, name))
            found = True
    return found


def find_param_file(station_id: str, file_id: str):
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(station_id or ""))[:64]
    safe_file = re.sub(r"[^A-Za-z0-9_-]", "", str(file_id or ""))
    if not safe_id or not safe_file:
        raise ValueError("文件标识不合法")
    folder = os.path.join(UPLOAD_DIR, safe_id)
    if not os.path.isdir(folder):
        raise FileNotFoundError("文件不存在")
    for name in os.listdir(folder):
        if name.split(".", 1)[0] == safe_file:
            path = os.path.join(folder, name)
            meta = {
                "id": safe_file,
                "name": name.split("_", 1)[1] if "_" in name else name,
                "path": f"{safe_id}/{name}",
            }
            return path, meta
    raise FileNotFoundError("文件不存在")


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


def _normalize_relation_items(value: Any, field: str, limit: int = 128) -> List[Dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(field + " 必须是数组")
    result: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        result.append({
            "code": code[:64],
            "name": str(item.get("name") or code).strip()[:limit],
        })
    return result


def normalize_config(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("工艺站点设计配置格式不正确")
    groups = payload.get("groups") or []
    stations = payload.get("stations") or []
    if not isinstance(groups, list) or not isinstance(stations, list):
        raise ValueError("分组和站点必须是数组")

    group_ids: set[str] = set()
    for group in groups:
        gid = str(group.get("id", "")).strip()
        if not gid or gid in group_ids:
            raise ValueError("分组 ID 不能为空且不能重复：" + gid)
        group_ids.add(gid)
        group["id"] = gid
        group["name"] = str(group.get("name") or gid)
        group["description"] = str(group.get("description") or "")
        group["order"] = int(group.get("order") or 1)

    library = payload.get("library") or _default_config()["library"]
    if not isinstance(library, list):
        raise ValueError("站点库必须是数组")
    library_codes: set[str] = set()
    library_names: Dict[str, str] = {}
    library_item_ids: set[str] = set()
    library_group_ids: set[str] = set()
    for lib_group in library:
        lib_id = str(lib_group.get("id", "")).strip()
        prefix = re.sub(r"[^A-Z0-9]", "", str(lib_group.get("prefix") or "").upper())[:8]
        if not lib_id or lib_id in library_group_ids:
            raise ValueError("站点库分组 ID 不能为空且不能重复：" + lib_id)
        if not prefix:
            raise ValueError(f"站点库分组 {lib_id} 缺少编码前缀")
        library_group_ids.add(lib_id)
        lib_group["id"] = lib_id
        lib_group["name"] = str(lib_group.get("name") or lib_id)
        lib_group["prefix"] = prefix
        lib_group["start"] = int(lib_group.get("start") or 1)
        lib_group["step"] = max(1, int(lib_group.get("step") or 10))
        lib_group["description"] = str(lib_group.get("description") or "")
        lib_group["order"] = int(lib_group.get("order") or 1)
        lib_items = lib_group.get("items") or []
        if not isinstance(lib_items, list):
            raise ValueError(f"站点库分组 {lib_id} 的条目必须是数组")
        for item in lib_items:
            item_id = str(item.get("id", "")).strip()
            code = re.sub(r"[^A-Z0-9-]", "", str(item.get("code") or "").upper())
            if not item_id or item_id in library_item_ids:
                raise ValueError("站点库条目 ID 不能为空且不能重复：" + item_id)
            if not code or not re.fullmatch(r"[A-Z][A-Z0-9-]{0,15}", code) or not code.startswith(prefix):
                raise ValueError(f"站点库编码不规范或不匹配前缀 {prefix}：" + code)
            if code in library_codes:
                raise ValueError("站点库编码不能重复：" + code)
            library_item_ids.add(item_id)
            library_codes.add(code)
            item["id"] = item_id
            item["code"] = code
            item["name"] = str(item.get("name") or code)
            library_names[code] = item["name"]
            item["type"] = str(item.get("type") or "normal")
            item["description"] = str(item.get("description") or "")
        lib_group["items"] = lib_items

    station_ids: set[str] = set()
    station_codes: set[str] = set()
    for station in stations:
        sid = str(station.get("id", "")).strip()
        code = str(station.get("code", "")).strip()
        if not sid or sid in station_ids:
            raise ValueError("站点 ID 不能为空且不能重复：" + sid)
        code = code.upper()
        if not code or code in station_codes:
            raise ValueError("站点编码不能为空且不能重复：" + code)
        if code not in library_codes:
            raise ValueError(f"站点编码 {code} 不在站点库中，请从站点库选择")
        gid = str(station.get("groupId", "")).strip()
        if gid not in group_ids:
            raise ValueError(f"站点 {code} 的分组不存在：" + gid)
        station_ids.add(sid)
        station_codes.add(code)
        station["id"] = sid
        station["code"] = code
        station["name"] = str(station.get("name") or library_names.get(code) or code)
        station["type"] = str(station.get("type") or "normal")
        station["groupId"] = gid
        station["order"] = int(station.get("order") or 1)
        station["enabled"] = bool(station.get("enabled", True))
        station["description"] = str(station.get("description") or "")
        station["workInstruction"] = str(station.get("workInstruction") or "")
        station["returnStationId"] = str(station.get("returnStationId") or "")

        params = station.get("params") or []
        param_files = station.get("paramFiles") or []
        fail_codes = station.get("failCodes") or []
        if not isinstance(params, list) or not isinstance(param_files, list) or not isinstance(fail_codes, list):
            raise ValueError(f"站点 {code} 的参数、参数附件和不良代码必须是数组")
        param_keys: set[str] = set()
        for param in params:
            key = str(param.get("key", "")).strip()
            if not key or key in param_keys:
                raise ValueError(f"站点 {code} 的参数标识不能为空且不能重复：" + key)
            param_keys.add(key)
            param["key"] = key
            param["label"] = str(param.get("label") or key)
            param["value"] = str(param.get("value") or "")
            param["unit"] = str(param.get("unit") or "")
            param["required"] = bool(param.get("required", False))
        fail_values: set[str] = set()
        for item in fail_codes:
            fail_code = str(item.get("code", "")).strip()
            if not fail_code or fail_code in fail_values:
                raise ValueError(f"站点 {code} 的不良代码不能为空且不能重复：" + fail_code)
            fail_values.add(fail_code)
            item["code"] = fail_code
            item["name"] = str(item.get("name") or fail_code)
        param_file_ids: set[str] = set()
        for meta in param_files:
            file_id = re.sub(r"[^A-Za-z0-9_-]", "", str(meta.get("id", "")))
            path = str(meta.get("path", ""))
            if not file_id or file_id in param_file_ids or "/" not in path or "\\" in path:
                raise ValueError(f"站点 {code} 的参数附件标识或路径不合法")
            if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.[a-z0-9]+", path):
                raise ValueError(f"站点 {code} 的参数附件路径不合法：" + path)
            param_file_ids.add(file_id)
            meta["id"] = file_id
            meta["name"] = str(meta.get("name") or file_id)[:180]
            meta["extension"] = str(meta.get("extension") or "").lower()[:10]
            meta["contentType"] = str(meta.get("contentType") or "application/octet-stream")[:120]
            meta["size"] = max(0, int(meta.get("size") or 0))
            meta["parseable"] = bool(meta.get("parseable", False))
            meta["uploadedAt"] = str(meta.get("uploadedAt") or _now())
            meta["path"] = path
        station["params"] = params
        station["paramFiles"] = param_files
        station["failCodes"] = fail_codes
        station["relatedProducts"] = _normalize_relation_items(station.get("relatedProducts"), "关联产品")
        station["relatedEquipment"] = _normalize_relation_items(station.get("relatedEquipment"), "关联设备")
        station["relatedPersons"] = _normalize_relation_items(station.get("relatedPersons"), "关联人员")

    for station in stations:
        return_id = station.get("returnStationId", "")
        if return_id and return_id not in station_ids:
            raise ValueError(f"站点 {station['code']} 的回站目标不存在：" + return_id)
        if return_id == station["id"]:
            raise ValueError(f"站点 {station['code']} 的回站目标不能是自己")

    settings = dict(payload.get("settings") or {})
    repair_id = str(settings.get("repairStationId") or "")
    if repair_id and repair_id not in station_ids:
        raise ValueError("维修站点不存在：" + repair_id)
    settings["assignPolicy"] = str(settings.get("assignPolicy") or "first")
    settings["snPoolScope"] = str(settings.get("snPoolScope") or "workOrder")
    settings["failCodeScope"] = str(settings.get("failCodeScope") or "station")
    settings["repairStationId"] = repair_id

    raw_options = payload.get("options") or {}
    raw_types = raw_options.get("stationTypes") or []
    if not isinstance(raw_types, list):
        raise ValueError("站点类型必须是数组")
    station_types: List[Dict[str, str]] = []
    type_values: set[str] = set()
    for item in raw_types:
        value = re.sub(r"[^a-z0-9_-]", "", str(item.get("value", "")).strip().lower())
        label = str(item.get("label", "")).strip()
        if not value or not label or value in type_values:
            raise ValueError("站点类型的值和名称不能为空且值不能重复：" + value)
        type_values.add(value)
        station_types.append({"value": value, "label": label})
    if not station_types:
        raise ValueError("至少保留一个站点类型")
    for group in library:
        for item in group.get("items", []):
            if item.get("type") not in type_values:
                raise ValueError(f"站点库项 {item['code']} 的类型未登记：" + item.get("type", ""))
    for station in stations:
        if station.get("type") not in type_values:
            raise ValueError(f"站点 {station['code']} 的类型未登记：" + station.get("type", ""))
    options = dict(raw_options)
    options["stationTypes"] = station_types
    return {
        "version": VERSION,
        "updatedAt": _now(),
        "groups": groups,
        "stations": stations,
        "library": library,
        "settings": settings,
        "options": options,
    }


def _sync_station_fields(config: Dict[str, Any], source: str) -> int:
    """按站点编码同步共享字段：name/type/description。"""
    shared = ("name", "type", "description")
    if source == "design":
        values = {
            str(s.get("code", "")).upper(): {field: str(s.get(field) or "") for field in shared}
            for s in config.get("stations", []) if s.get("code")
        }
        targets = [item for group in config.get("library", []) for item in group.get("items", [])]
    else:
        values = {
            str(item.get("code", "")).upper(): {field: str(item.get(field) or "") for field in shared}
            for group in config.get("library", []) for item in group.get("items", [])
            if item.get("code")
        }
        targets = list(config.get("stations", []))
    changed = 0
    for target in targets:
        code = str(target.get("code", "")).upper()
        source_values = values.get(code)
        if not source_values:
            continue
        for field in shared:
            wanted = source_values.get(field, "")
            if str(target.get(field) or "") != wanted:
                target[field] = wanted
                changed += 1
    return changed


def save_config(config: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    with _LOCK:
        changed = _sync_station_fields(config, "design")
        _write_raw(config)
        write_audit(
            db, actor, "process.design.save", "method",
            f"groups={len(config.get('groups', []))}; stations={len(config.get('stations', []))}; field_sync={changed}",
            commit=True,
        )
    return config


def master_snapshot() -> Dict[str, Any]:
    config = load_config()
    stations = config.get("stations", [])
    return {
        "groups": config.get("groups", []),
        "library": config.get("library", []),
        "libraryName": str(config.get("options", {}).get("libraryName") or "工位/站点主数据"),
        "stationTypes": config.get("options", {}).get("stationTypes", []),
        "usedGroupIds": sorted({str(s.get("groupId", "")) for s in stations if s.get("groupId")}),
        "usedLibraryCodes": sorted({str(s.get("code", "")).upper() for s in stations if s.get("code")}),
        "usedTypeValues": sorted({str(s.get("type", "")) for s in stations if s.get("type")}),
        "updatedAt": config.get("updatedAt", ""),
    }


def save_master_config(patch: Dict[str, Any], db: Session, actor: str) -> Dict[str, Any]:
    list_fields = {"groups", "library", "stationTypes"}
    text_fields = {"libraryName"}
    allowed = list_fields | text_fields
    unknown = set(patch or {}) - allowed
    if unknown:
        raise ValueError("主数据包含不支持的字段：" + "、".join(sorted(unknown)))
    with _LOCK:
        current = _read_raw()
        merged = copy.deepcopy(current)
        for key in list_fields:
            if key in patch:
                if not isinstance(patch[key], list):
                    raise ValueError(key + " 必须是数组")
                merged[key] = copy.deepcopy(patch[key])
        for key in text_fields:
            if key in patch:
                value = str(patch[key] or "").strip()[:128]
                if not value:
                    raise ValueError(key + " 不能为空")
                merged.setdefault("options", {})[key] = value
        if "stationTypes" in patch:
            merged.setdefault("options", {})["stationTypes"] = merged.pop("stationTypes")
        config = normalize_config(merged)
        changed = _sync_station_fields(config, "library")
        _write_raw(config)
        write_audit(
            db, actor, "process.master.save", "environment",
            f"groups={len(config.get('groups', []))}; library={len(config.get('library', []))}; field_sync={changed}",
            commit=True,
        )
    return config
