"""环境配置 · 全局资料库存储。

文件本体与元数据分离保存；元数据使用临时文件 + os.replace 原子替换。
只负责资料文件，不读取或改写人员、工艺、工单等业务数据。
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "environment_resources.json")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "environment")
MAX_FILE_SIZE = 200 * 1024 * 1024
# 关联字段与 relation_store 的跨模块规范保持一致：站点（工艺/工站）统一叫 relatedStations。
RELATION_FIELDS = ("relatedPersons", "relatedProducts", "relatedEquipment", "relatedStations")
# 历史版本把站点关联存为 relatedProcesses，读取时按旧名兼容。
LEGACY_RELATION_ALIASES = {"relatedProcesses": "relatedStations"}
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _default_config() -> Dict[str, Any]:
    return {"version": 1, "updatedAt": _now(), "resources": []}


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
    config.setdefault("version", 1)
    config.setdefault("updatedAt", _now())
    config.setdefault("resources", [])
    return config


def _write_raw(config: Dict[str, Any]) -> None:
    config["updatedAt"] = _now()
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
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


def _normalize_relation_items(value: Any, field: str) -> List[Dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(field + " 必须是数组")
    items: List[Dict[str, str]] = []
    seen: set[str] = set()
    for raw in value:
        if isinstance(raw, dict):
            code = str(raw.get("code") or "").strip()
            name = str(raw.get("name") or code).strip()
        else:
            code = str(raw or "").strip()
            name = code
        if not code or code in seen:
            continue
        seen.add(code)
        items.append({"code": code[:64], "name": name[:128]})
    return items


def _relation_text(row: Dict[str, Any]) -> str:
    values: List[str] = []
    for field in RELATION_FIELDS:
        values.extend(str(item.get("name") or item.get("code") or "") for item in row.get(field) or [])
    return " ".join(v for v in values if v)


def _migrate_legacy_relations(row: Dict[str, Any]) -> Dict[str, Any]:
    """把旧字段 relatedProcesses 迁移到 relatedStations，返回同一行对象。"""
    for legacy, current in LEGACY_RELATION_ALIASES.items():
        if legacy not in row:
            continue
        legacy_items = row.get(legacy) or []
        current_items = row.get(current) or []
        if legacy_items and not current_items:
            row[current] = legacy_items
        row.pop(legacy, None)
    return row


def _history_entry(version: int, action: str, actor: str, note: str) -> Dict[str, str]:
    return {
        "version": str(version),
        "action": action,
        "at": _now(),
        "by": actor,
        "note": note[:200],
    }


def list_resources(module: str = "", category: str = "", q: str = "") -> List[Dict[str, Any]]:
    rows = _read_raw().get("resources", [])
    needle = str(q or "").strip().lower()
    result = []
    for row in rows:
        row.setdefault("version", 1)
        row.setdefault("history", [_history_entry(1, "upload", str(row.get("uploadedBy") or ""), "首次上传")])
        _migrate_legacy_relations(row)
        for field in RELATION_FIELDS:
            row.setdefault(field, [])
        if module and str(row.get("module", "")) != module:
            continue
        if category and str(row.get("category", "")) != category:
            continue
        if needle and needle not in " ".join([
            str(row.get("title", "")), str(row.get("fileName", "")),
            str(row.get("category", "")), str(row.get("description", "")),
            _relation_text(row),
        ]).lower():
            continue
        result.append(row)
    return sorted(result, key=lambda r: r.get("updatedAt") or r.get("uploadedAt", ""), reverse=True)


def resource_meta(payload: Dict[str, Any], size: int) -> Dict[str, Any]:
    filename = os.path.basename(str(payload.get("fileName") or ""))[:180] or "未命名附件"
    ext = os.path.splitext(filename)[1].lower()
    ext = re.sub(r"[^.a-z0-9]", "", ext)[:16]
    if not ext or ext == ".":
        ext = ".bin"
    if size <= 0 or size > MAX_FILE_SIZE:
        raise ValueError("文件不能为空且不能超过 200MB")
    file_id = uuid.uuid4().hex
    actor = _text(payload.get("uploadedBy"), "上传人", limit=64)
    now = _now()
    meta = {
        "id": file_id,
        "title": _text(payload.get("title"), "资料标题", True, 128),
        "module": _text(payload.get("module"), "所属模块", True, 64),
        "category": _text(payload.get("category"), "资料类别", True, 64),
        "description": _text(payload.get("description"), "说明", limit=500),
        "fileName": filename,
        "extension": ext,
        "contentType": str(payload.get("contentType") or "application/octet-stream")[:120],
        "size": int(size),
        "uploadedAt": now,
        "uploadedBy": actor,
        "updatedAt": now,
        "updatedBy": actor,
        "version": 1,
        "history": [_history_entry(1, "upload", actor, "首次上传")],
        "path": file_id + ext,
    }
    for field in RELATION_FIELDS:
        meta[field] = _normalize_relation_items(payload.get(field), field)
    # 旧字段只作兜底：新字段有值时以新字段为准，避免旧空值覆盖新数据。
    for legacy, current in LEGACY_RELATION_ALIASES.items():
        if legacy in payload and not meta.get(current):
            meta[current] = _normalize_relation_items(payload.get(legacy), current)
    return meta


def create_resource(meta: Dict[str, Any], content: bytes) -> Dict[str, Any]:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    target = os.path.join(UPLOAD_DIR, meta["path"])
    tmp = target + ".tmp"
    with open(tmp, "wb") as f:
        f.write(content)
    os.replace(tmp, target)
    with _LOCK:
        config = _read_raw()
        config.setdefault("resources", []).append(meta)
        _write_raw(config)
    return meta


def find_resource(resource_id: str) -> Dict[str, Any]:
    key = re.sub(r"[^A-Za-z0-9_-]", "", str(resource_id or ""))
    return next((r for r in _read_raw().get("resources", []) if str(r.get("id")) == key), None)  # type: ignore[return-value]


def update_resource(resource_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        config = _read_raw()
        target = None
        for row in config.get("resources", []):
            if str(row.get("id")) != resource_id:
                continue
            changed = False
            for field in ["title", "module", "category", "description"]:
                if field in payload:
                    value = _text(payload.get(field), field, field != "description", 500 if field == "description" else 128)
                    if str(row.get(field) or "") != value:
                        row[field] = value
                        changed = True
            for field in RELATION_FIELDS:
                if field in payload:
                    value = _normalize_relation_items(payload.get(field), field)
                    if (row.get(field) or []) != value:
                        row[field] = value
                        changed = True
            for legacy, current in LEGACY_RELATION_ALIASES.items():
                if legacy in payload and not payload.get(current):
                    value = _normalize_relation_items(payload.get(legacy), current)
                    if (row.get(current) or []) != value:
                        row[current] = value
                        changed = True
            version_note = str(payload.get("versionNote") or "").strip()
            if version_note:
                changed = True
            if changed:
                actor = _text(payload.get("updatedBy"), "更新人", limit=64)
                row["version"] = int(row.get("version") or 1) + 1
                row["updatedAt"] = _now()
                row["updatedBy"] = actor
                row.setdefault("history", []).append(_history_entry(
                    int(row["version"]), "update", actor,
                    str(payload.get("versionNote") or "资料信息更新"),
                ))
            target = row
            break
        if not target:
            raise ValueError("资料不存在")
        _write_raw(config)
        return target


def delete_resource(resource_id: str) -> Dict[str, Any]:
    with _LOCK:
        config = _read_raw()
        target = None
        for row in config.get("resources", []):
            if str(row.get("id")) == resource_id:
                target = row
                break
        if not target:
            raise ValueError("资料不存在")
        config["resources"] = [r for r in config.get("resources", []) if str(r.get("id")) != resource_id]
        _write_raw(config)
    path = os.path.join(UPLOAD_DIR, str(target.get("path") or ""))
    if os.path.isfile(path):
        os.remove(path)
    return target


def resource_path(resource: Dict[str, Any]) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]", "", str(resource.get("path") or ""))
    path = os.path.join(UPLOAD_DIR, name)
    if not os.path.isfile(path):
        raise FileNotFoundError("资料文件不存在")
    return path
