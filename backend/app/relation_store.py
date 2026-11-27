"""跨模块关联关系：产品、设备、人员、站点、工单共用同一套关系字段。"""
import json
import os
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from . import models, relation_items

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "relation_links.json")
_LOCK = threading.Lock()
VERSION = 1

KINDS = ("station", "product", "equipment", "person", "workOrder")
RELATION_FIELDS = {
    "station": ("relatedProducts", "relatedEquipment", "relatedPersons", "relatedWorkOrders"),
    "product": ("relatedStations", "relatedEquipment", "relatedPersons", "relatedWorkOrders"),
    "equipment": ("relatedStations", "relatedProducts", "relatedPersons", "relatedWorkOrders"),
    "person": ("relatedStations", "relatedProducts", "relatedEquipment", "relatedWorkOrders"),
    "workOrder": ("relatedStations", "relatedProducts", "relatedEquipment", "relatedPersons"),
}
TARGET_KIND = {
    "relatedStations": "station",
    "relatedProducts": "product",
    "relatedEquipment": "equipment",
    "relatedPersons": "person",
    "relatedWorkOrders": "workOrder",
}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _default_config() -> Dict[str, Any]:
    return {"version": VERSION, "updatedAt": _now(), "edges": []}


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
        return config
    config.setdefault("version", VERSION)
    config.setdefault("updatedAt", _now())
    config.setdefault("edges", [])
    return config


def _write_raw(config: Dict[str, Any]) -> None:
    config["version"] = VERSION
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, DATA_FILE)


def _entity(kind: str, code: Any) -> Optional[Tuple[str, str]]:
    key = str(code or "").strip()
    if not key:
        return None
    return kind, key.upper() if kind in ("product", "equipment") else key


def _edge(row: Dict[str, Any]) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    left = _entity(str(row.get("sourceKind") or ""), row.get("sourceCode"))
    right = _entity(str(row.get("targetKind") or ""), row.get("targetCode"))
    return (left or ("", "")), (right or ("", ""))


def normalize_edges(db) -> int:
    """把历史关系中按姓名保存的人员编码统一为登录账号。"""
    accounts = db.query(models.Account).all()
    usernames = {str(row.username or "").strip() for row in accounts if row.username}
    by_name = {str(row.name or "").strip(): str(row.username or "").strip() for row in accounts if row.name and row.username}
    changed = 0
    with _LOCK:
        config = _read_raw()
        for row in config.get("edges", []):
            for kind_field, code_field in (("sourceKind", "sourceCode"), ("targetKind", "targetCode")):
                if str(row.get(kind_field) or "") != "person":
                    continue
                code = str(row.get(code_field) or "").strip()
                account = by_name.get(code, code)
                if account in usernames and account != code:
                    row[code_field] = account
                    changed += 1
        if changed:
            _write_raw(config)
    return changed


def replace_source_edges(source_kind: str, source_code: Any, relations: Dict[str, Any]) -> int:
    """替换某个对象主动声明的关联边；同步回写的字段不会作为来源。"""
    source = _entity(source_kind, source_code)
    if not source:
        return 0
    wanted: Set[Tuple[str, str]] = set()
    for field, target_kind in TARGET_KIND.items():
        if field not in (relations or {}):
            continue
        for item in relation_items.normalize_items(relations.get(field)):
            target = _entity(target_kind, item.get("code"))
            if target and target != source:
                wanted.add(target)
    with _LOCK:
        config = _read_raw()
        kept = [row for row in config.get("edges", []) if _edge(row)[0] != source]
        for target in sorted(wanted):
            kept.append({
                "sourceKind": source[0], "sourceCode": source[1],
                "targetKind": target[0], "targetCode": target[1],
            })
        config["edges"] = kept
        _write_raw(config)
    return len(wanted)


def set_work_order_relations(wo_no: str, relations: Dict[str, Any]) -> int:
    return replace_source_edges("workOrder", wo_no, relations)


def source_relations(kind: str, code: Any, db=None) -> Dict[str, List[Dict[str, str]]]:
    if db is not None:
        normalize_edges(db)
    node = _entity(kind, code)
    result = {field: [] for field in RELATION_FIELDS.get(kind, ())}
    if not node:
        return result
    groups: Dict[str, List[str]] = defaultdict(list)
    for row in _read_raw().get("edges", []):
        left, right = _edge(row)
        if left == node:
            groups[right[0]].append(right[1])
    for field in RELATION_FIELDS.get(kind, ()):
        target_kind = TARGET_KIND[field]
        result[field] = items_for(target_kind, groups.get(target_kind, []), db) if db else [
            {"code": item, "name": item} for item in groups.get(target_kind, [])
        ]
    return result


def update_source_relations(kind: str, code: Any, relations: Dict[str, Any]) -> int:
    """保存某个对象的主动勾选；自动关联项不写入来源边。"""
    source = _entity(kind, code)
    if not source:
        return 0
    current = source_relations(kind, code)
    merged = dict(current)
    for field in RELATION_FIELDS.get(kind, ()):
        merged[field] = relation_items.normalize_items((relations or {}).get(field, current.get(field, [])))
    return replace_source_edges(kind, code, merged)


def device_relations(device: Dict[str, Any], db, payload: Dict[str, Any] = None) -> Dict[str, List[Dict[str, str]]]:
    """把设备旧字段 stationCode/productCode/operator 转成统一字段；表单显式传空时按清空处理。"""
    result: Dict[str, List[Dict[str, str]]] = {}
    for field, legacy in (("relatedStations", "stationCode"), ("relatedProducts", "productCode"), ("relatedPersons", "operator")):
        if payload is not None and legacy in (payload or {}):
            value = str((payload or {}).get(legacy) or "").strip()
            items = []
            if value:
                target_kind = TARGET_KIND[field]
                items = [{"code": resolve_relation_code(target_kind, value, db), "name": value}]
        else:
            items = relation_items.normalize_items((device or {}).get(field))
            if not items:
                value = str((device or {}).get(legacy) or "").strip()
                if value:
                    target_kind = TARGET_KIND[field]
                    items = [{"code": resolve_relation_code(target_kind, value, db), "name": value}]
        result[field] = items
    return result


def apply_full_selection(kind: str, code: Any, desired: Dict[str, Any], db) -> int:
    """根据表单完整勾选更新主动来源；已自动关联项不会被误记为手工来源。"""
    source = _entity(kind, code)
    if not source:
        return 0
    current_effective = relations_for(kind, source[1], db)
    current_source = source_relations(kind, source[1], db)
    result: Dict[str, List[Dict[str, str]]] = {}
    for field in RELATION_FIELDS.get(kind, ()):
        desired_items = relation_items.normalize_items((desired or {}).get(field, current_effective.get(field, [])))
        desired_codes = {item["code"] for item in desired_items}
        effective_codes = {item["code"] for item in current_effective.get(field, [])}
        source_items = current_source.get(field, [])
        source_codes = {item["code"] for item in source_items}
        next_codes = source_codes - (effective_codes - desired_codes) | (desired_codes - effective_codes)
        result[field] = [item for item in desired_items if item["code"] in next_codes]
        result[field] += [item for item in source_items if item["code"] in next_codes and item["code"] not in desired_codes]
    return replace_source_edges(kind, source[1], result)


def resolve_relation_code(kind: str, value: Any, db) -> str:
    """把产品/站点名称解析成统一关系编码。

    先按 code 精确匹配，再按 name 匹配：同名产品存在时（如两个产品都叫
    "V2.9 无本体数采背包"），只有先比 code 才不会关联到错对象。
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    items = options(db).get({"product": "products", "station": "stations", "equipment": "equipment", "person": "persons"}.get(kind, ""), [])
    for item in items:
        if raw.lower() == str(item.get("code") or "").lower():
            return str(item.get("code") or "")
    for item in items:
        if raw.lower() == str(item.get("name") or "").lower():
            return str(item.get("code") or "")
    return raw


def remove_source(kind: str, code: Any) -> int:
    source = _entity(kind, code)
    if not source:
        return 0
    with _LOCK:
        config = _read_raw()
        before = len(config.get("edges", []))
        config["edges"] = [row for row in config.get("edges", []) if _edge(row)[0] != source]
        _write_raw(config)
        return before - len(config["edges"])


def _bootstrap(db) -> None:
    """首次运行时把现有字段转成统一关系边，之后只认关系库。"""
    from . import equipment_store, personnel_store, process_design_store, product_profiles_store

    config = _read_raw()
    if config.get("edges"):
        return
    edges: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    def add(source: Optional[Tuple[str, str]], target: Optional[Tuple[str, str]]) -> None:
        if not source or not target or source == target:
            return
        key = (source[0], source[1], target[0], target[1])
        if key in seen:
            return
        seen.add(key)
        edges.append({
            "sourceKind": source[0], "sourceCode": source[1],
            "targetKind": target[0], "targetCode": target[1],
        })

    for station in process_design_store.load_config().get("stations", []):
        node = _entity("station", station.get("code") or station.get("id"))
        for field, kind in (("relatedProducts", "product"), ("relatedEquipment", "equipment"), ("relatedPersons", "person")):
            for item in relation_items.normalize_items(station.get(field)):
                add(node, _entity(kind, item.get("code")))
    accounts = db.query(models.Account).all()
    person_by_name = {str(row.name or "").strip(): str(row.username or "").strip() for row in accounts if row.name and row.username}
    for device in equipment_store.list_devices():
        node = _entity("equipment", device.get("code"))
        add(node, _entity("station", device.get("stationCode")))
        add(node, _entity("product", device.get("productCode")))
        operator = str(device.get("operator") or "").strip()
        add(node, _entity("person", person_by_name.get(operator, operator)))
    for person in personnel_store.list_persons():
        node = _entity("person", person.get("username"))
        for field, kind in (("relatedStations", "station"), ("relatedProducts", "product"), ("relatedEquipment", "equipment")):
            for item in relation_items.normalize_items(person.get(field)):
                add(node, _entity(kind, item.get("code")))
    profile_by_name = {str(item.get("name") or "").strip(): _entity("product", item.get("code"))
                       for item in product_profiles_store.list_profiles()}
    for wo in db.query(models.WorkOrder).all():
        node = _entity("workOrder", wo.wo_no)
        product = profile_by_name.get(str(wo.product or "").strip()) or _entity("product", wo.product)
        add(node, product)
        for station in wo.stations or []:
            add(node, _entity("station", station))

    config["edges"] = edges
    _write_raw(config)


def _add(adjacency: Dict[Tuple[str, str], Set[Tuple[str, str]]], left: Any, right: Any) -> None:
    if not left or not right or left == right:
        return
    adjacency[left].add(right)
    adjacency[right].add(left)


def _connect_group(adjacency: Dict[Tuple[str, str], Set[Tuple[str, str]]], nodes: Iterable[Tuple[str, str]]) -> None:
    items = [node for node in nodes if node]
    for index, left in enumerate(items):
        for right in items[index + 1:]:
            if left[0] != right[0]:
                _add(adjacency, left, right)


def build_relations(db) -> Dict[Tuple[str, str], Set[Tuple[str, str]]]:
    from . import models

    normalize_edges(db)
    _bootstrap(db)
    adjacency: Dict[Tuple[str, str], Set[Tuple[str, str]]] = defaultdict(set)
    for row in _read_raw().get("edges", []):
        left, right = _edge(row)
        if left[0] in KINDS and right[0] in KINDS:
            adjacency[left]
            adjacency[right]
            _add(adjacency, left, right)
    for node, targets in list(adjacency.items()):
        if node[0] == "station":
            _connect_group(adjacency, [node] + [target for target in targets if target[0] in ("product", "equipment", "person", "workOrder")])
    for node, targets in list(adjacency.items()):
        if node[0] == "workOrder":
            _connect_group(adjacency, [node] + [target for target in targets if target[0] in ("product", "equipment", "person", "station")])
    return adjacency


def _names(db) -> Dict[Tuple[str, str], str]:
    from . import equipment_store, models, process_design_store, product_profiles_store

    result: Dict[Tuple[str, str], str] = {}
    for item in process_design_store.load_config().get("stations", []):
        code = str(item.get("code") or item.get("id") or "").strip()
        if code:
            result[("station", code)] = str(item.get("name") or code)
    for item in product_profiles_store.list_profiles():
        code = str(item.get("code") or "").strip().upper()
        if code:
            result[("product", code)] = str(item.get("name") or code)
    for item in equipment_store.list_devices():
        code = str(item.get("code") or "").strip().upper()
        if code:
            result[("equipment", code)] = str(item.get("name") or code)
    for row in db.query(models.Account).all():
        username = str(row.username or "").strip()
        if username:
            result[("person", username)] = str(row.name or username)
    for row in db.query(models.WorkOrder).all():
        code = str(row.wo_no or "").strip()
        if code:
            result[("workOrder", code)] = code
    return result


def items_for(kind: str, codes: Iterable[str], db, names: Optional[Dict[Tuple[str, str], str]] = None) -> List[Dict[str, str]]:
    names = names if names is not None else _names(db)
    result: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for code in codes:
        key = str(code or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({"code": key, "name": names.get((kind, key), key)})
    return result


def relations_for(kind: str, code: str, db, adjacency=None, names=None) -> Dict[str, List[Dict[str, str]]]:
    adjacency = adjacency if adjacency is not None else build_relations(db)
    names = names if names is not None else _names(db)
    node = _entity(kind, code)
    result: Dict[str, List[Dict[str, str]]] = {}
    if not node:
        return {field: [] for field in RELATION_FIELDS.get(kind, ())}
    for field in RELATION_FIELDS.get(kind, ()):
        target_kind = TARGET_KIND[field]
        codes = sorted(target[1] for target in adjacency.get(node, set()) if target[0] == target_kind)
        result[field] = items_for(target_kind, codes, db, names)
    return result


def enrich_process_design(config: Dict[str, Any], db, adjacency=None, names=None) -> Dict[str, Any]:
    adjacency = adjacency if adjacency is not None else build_relations(db)
    names = names if names is not None else _names(db)
    result = json.loads(json.dumps(config or {}))
    for station in result.get("stations", []):
        code = str(station.get("code") or station.get("id") or "").strip()
        related = relations_for("station", code, db, adjacency, names)
        for field in ("relatedProducts", "relatedEquipment", "relatedPersons"):
            station[field] = related.get(field, [])
    return result


def enrich_device(device: Dict[str, Any], db, adjacency=None, names=None) -> Dict[str, Any]:
    adjacency = adjacency if adjacency is not None else build_relations(db)
    names = names if names is not None else _names(db)
    result = dict(device or {})
    result.update(relations_for("equipment", result.get("code"), db, adjacency, names))
    return result


def enrich_person(person: Dict[str, Any], db, adjacency=None, names=None) -> Dict[str, Any]:
    adjacency = adjacency if adjacency is not None else build_relations(db)
    names = names if names is not None else _names(db)
    result = dict(person or {})
    result.update(relations_for("person", result.get("username"), db, adjacency, names))
    return result


def enrich_work_order(wo: Dict[str, Any], db, adjacency=None, names=None) -> Dict[str, Any]:
    adjacency = adjacency if adjacency is not None else build_relations(db)
    names = names if names is not None else _names(db)
    result = dict(wo or {})
    result.update(relations_for("workOrder", result.get("wo_no"), db, adjacency, names))
    return result


def _apply_station_fields(config: Dict[str, Any], db, adjacency, names) -> None:
    for station in config.get("stations", []):
        related = relations_for("station", station.get("code") or station.get("id"), db, adjacency, names)
        for field in ("relatedProducts", "relatedEquipment", "relatedPersons"):
            station[field] = related.get(field, [])


def _apply_device_fields(config: Dict[str, Any], db, adjacency, names) -> None:
    for device in config.get("devices", []):
        related = relations_for("equipment", device.get("code"), db, adjacency, names)
        for field in ("relatedStations", "relatedProducts", "relatedPersons"):
            device[field] = related.get(field, [])
        stations = related.get("relatedStations", [])
        products = related.get("relatedProducts", [])
        persons = related.get("relatedPersons", [])
        if stations:
            device["stationCode"] = stations[0]["code"]
            device["stationName"] = stations[0]["name"]
        if products:
            device["productCode"] = products[0]["code"]
            device["productName"] = products[0]["name"]
        if persons:
            device["operator"] = persons[0]["code"]


def _apply_person_fields(config: Dict[str, Any], db, adjacency, names) -> None:
    for person in config.get("persons", []):
        related = relations_for("person", person.get("username"), db, adjacency, names)
        for field in ("relatedStations", "relatedProducts", "relatedEquipment"):
            person[field] = related.get(field, [])


def _apply_product_fields(config: Dict[str, Any], db, adjacency, names) -> None:
    for product in config.get("products", []):
        related = relations_for("product", product.get("code"), db, adjacency, names)
        for field in ("relatedStations", "relatedEquipment", "relatedPersons"):
            product[field] = related.get(field, [])


def sync_all(db) -> Dict[str, int]:
    from . import equipment_store, personnel_store, process_design_store, product_profiles_store

    adjacency = build_relations(db)
    names = _names(db)
    counts = {"stations": 0, "equipment": 0, "persons": 0, "products": 0}

    process_config = process_design_store._read_raw()
    _apply_station_fields(process_config, db, adjacency, names)
    process_design_store._write_raw(process_config)
    counts["stations"] = len(process_config.get("stations", []))

    equipment_config = equipment_store._read_raw()
    _apply_device_fields(equipment_config, db, adjacency, names)
    equipment_store._write_raw(equipment_config)
    counts["equipment"] = len(equipment_config.get("devices", []))

    personnel_config = personnel_store._read_raw()
    _apply_person_fields(personnel_config, db, adjacency, names)
    personnel_store._write_raw(personnel_config)
    counts["persons"] = len(personnel_config.get("persons", []))

    product_config = product_profiles_store._read_raw()
    _apply_product_fields(product_config, db, adjacency, names)
    product_profiles_store._write_raw(product_config)
    counts["products"] = len(product_config.get("products", []))

    return counts


def options(db) -> Dict[str, Any]:
    from . import equipment_store, models, process_design_store, product_profiles_store

    return {
        "products": [
            {"code": str(item.get("code") or "").upper(), "name": str(item.get("name") or "")}
            for item in product_profiles_store.list_profiles() if item.get("code")
        ],
        "equipment": [
            {"code": str(item.get("code") or "").upper(), "name": str(item.get("name") or "")}
            for item in equipment_store.list_devices() if item.get("code")
        ],
        "persons": [
            {"code": row.username, "name": row.name or row.username}
            for row in db.query(models.Account).order_by(models.Account.name.asc()).all()
        ],
        "stations": [
            {"code": str(item.get("code") or "").upper(), "name": str(item.get("name") or "")}
            for item in process_design_store.load_config().get("stations", []) if item.get("code")
        ],
    }
