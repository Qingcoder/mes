"""产品资料与SN清单数据层。

使用独立 JSON 配置保存产品资料，写入采用临时文件 + os.replace 原子替换。
产品编码与 SN 全局唯一；所有写操作先校验，再整体替换配置，避免半写入。
"""
import json
import os
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import relation_items

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "product_profiles.json")
_LOCK = threading.Lock()
PRODUCT_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,63}$")
SN_RE = re.compile(r"^[A-Z0-9]{16}$")


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _read_raw() -> Dict[str, Any]:
    with _LOCK:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def _write_raw(config: Dict[str, Any]) -> None:
    config["updatedAt"] = _now()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, DATA_FILE)


def _mutate(action) -> Any:
    with _LOCK:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        result = action(config)
        _write_raw(config)
        return result


def list_profiles() -> List[Dict[str, Any]]:
    return _read_raw().get("products", [])


def find_product(value: str) -> Optional[Dict[str, Any]]:
    """仅按显式产品编码或产品名称精确查找，不按系列/文件名推断产品。"""
    key = str(value or "").strip().lower()
    if not key:
        return None
    for product in list_profiles():
        if key in {
            str(product.get("code", "")).lower(),
            str(product.get("name", "")).lower(),
        }:
            return product
    return None


def find_product_by_code(code: str) -> Optional[Dict[str, Any]]:
    key = str(code or "").strip().upper()
    return next((p for p in list_profiles() if str(p.get("code", "")).upper() == key), None)


def basic_product(code: str, name: str, family: str = "", left_prefix: str = "Z", right_prefix: str = "Y") -> Dict[str, Any]:
    payload = {
        "code": code,
        "name": name,
        "family": family,
        "description": "",
        "batchDate": "",
        "sourceFiles": [],
        "snRule": {"length": 16, "leftPrefix": left_prefix, "rightPrefix": right_prefix, "sideBy": "SN 前缀"},
        "specs": [], "functions": [], "scenarios": [],
        "sides": [
            {"key": "left", "name": "左件", "prefix": left_prefix, "fileName": "", "sns": []},
            {"key": "right", "name": "右件", "prefix": right_prefix, "fileName": "", "sns": []},
        ],
    }
    product = _normalize_product(payload)
    product["snRows"] = []
    return product


def side_of_sn(product: Dict[str, Any], sn: str) -> Optional[Dict[str, Any]]:
    value = str(sn or "").strip().upper()
    rule = product.get("snRule") or {}
    for side in product.get("sides", []):
        if value.startswith(str(side.get("prefix") or "").upper()):
            return side
    if len(value) == int(rule.get("length") or 16) and value[3:4] == "Z":
        return next((s for s in product.get("sides", []) if s.get("key") == "left"), None)
    if len(value) == int(rule.get("length") or 16) and value[3:4] == "Y":
        return next((s for s in product.get("sides", []) if s.get("key") == "right"), None)
    return None


def lookup_sn(sn: str) -> Optional[Dict[str, Any]]:
    """只按已导入 SN 精确查找，不根据 SN 前缀猜产品。"""
    value = str(sn or "").strip().upper()
    if not value:
        return None
    for product in list_profiles():
        for side in product.get("sides", []):
            if any(str(item).strip().upper() == value for item in side.get("sns", [])):
                result = dict(product)
                result["matchedSide"] = side
                result["matchedSn"] = value
                result["found"] = True
                return result
    return None


def product_sn_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for side in product.get("sides", []):
        for sn in side.get("sns", []):
            rows.append({
                "sn": str(sn).strip().upper(),
                "sideKey": side.get("key", ""),
                "sideName": side.get("name", ""),
                "prefix": side.get("prefix", ""),
            })
    return rows


def _sn_master_entries() -> List[Dict[str, Any]]:
    config = _read_raw()
    updated_at = str(config.get("updatedAt") or "")
    entries: List[Dict[str, Any]] = []
    for product in config.get("products", []):
        code = str(product.get("code") or "")
        name = str(product.get("name") or code)
        for side in product.get("sides", []):
            source_file = str(side.get("fileName") or "")
            side_key = str(side.get("key") or "")
            side_name = str(side.get("name") or "")
            for raw_sn in side.get("sns", []):
                sn = str(raw_sn or "").strip().upper()
                if not sn:
                    continue
                entries.append({
                    "sn": sn,
                    "product": name,
                    "productCode": code,
                    "sideKey": side_key,
                    "sideName": side_name,
                    "sourceFile": source_file,
                    "updatedAt": updated_at,
                })
    return entries


def sn_master_records() -> List[Dict[str, Any]]:
    """从产品资料总表汇总 SN 主数据，重复 SN 只保留第一条。"""
    seen: set[str] = set()
    rows: List[Dict[str, Any]] = []
    for entry in _sn_master_entries():
        sn = entry["sn"]
        if sn in seen:
            continue
        seen.add(sn)
        rows.append({
            "id": sn, **entry,
            "remark": " / ".join(item for item in [entry["sideName"], entry["sourceFile"]] if item),
        })
    return rows


def sn_master_duplicates() -> List[Dict[str, Any]]:
    """列出产品资料总表中被 SN 库去重合并的重复 SN 及其来源。"""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in _sn_master_entries():
        grouped.setdefault(entry["sn"], []).append({
            "product": entry["product"],
            "productCode": entry["productCode"],
            "sideName": entry["sideName"],
            "sourceFile": entry["sourceFile"],
        })
    return [
        {"sn": sn, "count": len(sources), "removed": len(sources) - 1, "sources": sources}
        for sn, sources in grouped.items() if len(sources) > 1
    ]


def detail(code: str) -> Dict[str, Any]:
    product = find_product_by_code(code)
    if not product:
        raise ValueError("产品资料不存在")
    result = dict(product)
    result["snRows"] = product_sn_rows(product)
    return result


def validate_sn_prefix(sn: str) -> bool:
    value = str(sn or "").strip().upper()
    return bool(SN_RE.fullmatch(value))


def _normalize_code(value: Any, field: str = "产品编码") -> str:
    code = str(value or "").strip().upper()
    if not PRODUCT_CODE_RE.fullmatch(code):
        raise ValueError(f"{field}需以大写字母开头，仅含 2-64 位大写字母、数字、下划线或短横线")
    return code


def _normalize_sn(value: Any) -> str:
    sn = str(value or "").strip().upper()
    if not SN_RE.fullmatch(sn):
        raise ValueError("SN 必须为 16 位大写字母或数字：" + (sn or "空"))
    return sn


def _normalize_text(value: Any, field: str, required: bool = False, limit: int = 500) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field}不能为空")
    if len(text) > limit:
        raise ValueError(f"{field}不能超过 {limit} 字符")
    return text


def _normalize_rows(value: Any, fields: List[str], label: str, limit: int = 100) -> List[Dict[str, str]]:
    rows = value or []
    if not isinstance(rows, list):
        raise ValueError(label + "必须是数组")
    if len(rows) > limit:
        raise ValueError(f"{label}最多 {limit} 条")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(label + "的每一行必须是对象")
        item = {field: _normalize_text(row.get(field), field, limit=200) for field in fields}
        if not any(item.values()):
            continue
        if not all(item[field] for field in fields):
            raise ValueError(label + "的每一行必须填写完整")
        result.append(item)
    return result


def _product_sns(product: Dict[str, Any]) -> List[str]:
    return [str(sn).strip().upper() for side in product.get("sides", []) for sn in side.get("sns", [])]


def _ensure_unique(config: Dict[str, Any], product_code: str, sns: List[str]) -> None:
    seen: set[str] = set()
    for other in config.get("products", []):
        if str(other.get("code", "")).upper() == product_code:
            continue
        for sn in _product_sns(other):
            if sn in sns:
                raise ValueError(f"SN {sn} 已属于产品 {other.get('code', '')}")
            seen.add(sn)
    for sn in sns:
        if sns.count(sn) > 1:
            raise ValueError(f"SN 重复：{sn}")


def _normalize_sides(value: Any) -> List[Dict[str, Any]]:
    sides = value or []
    if not isinstance(sides, list):
        raise ValueError("件别必须是数组")
    if len(sides) > 20:
        raise ValueError("件别最多 20 个")
    result: List[Dict[str, Any]] = []
    keys: set[str] = set()
    for raw in sides:
        if not isinstance(raw, dict):
            raise ValueError("件别必须是对象")
        key = _normalize_text(raw.get("key"), "件别标识", True, 32).lower()
        if key in keys:
            raise ValueError("件别标识不能重复：" + key)
        keys.add(key)
        sns = raw.get("sns") or []
        if not isinstance(sns, list):
            raise ValueError("SN 清单必须是数组")
        result.append({
            "key": key,
            "name": _normalize_text(raw.get("name"), "件别名称", True, 64),
            "prefix": _normalize_text(raw.get("prefix"), "SN 前缀", key != "sn", 16).upper(),
            "fileName": _normalize_text(raw.get("fileName"), "来源文件", limit=180),
            "sns": [_normalize_sn(sn) for sn in sns],
        })
    if not result:
        raise ValueError("至少保留一个件别")
    return result


def _normalize_product(payload: Dict[str, Any], existing_code: str = "") -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("产品资料必须是对象")
    requested_code = str(payload.get("code") or existing_code or "").strip().upper()
    code = _normalize_code(requested_code)
    if existing_code and code != existing_code:
        raise ValueError("产品编码不允许修改")
    product = {
        "code": code,
        "name": _normalize_text(payload.get("name"), "产品名称", True, 128),
        "family": _normalize_text(payload.get("family"), "产品系列", limit=128),
        "description": _normalize_text(payload.get("description"), "产品描述", limit=800),
        "batchDate": _normalize_text(payload.get("batchDate"), "批次日期", limit=32),
        "snRule": {
            "length": int(payload.get("snRule", {}).get("length") or 16),
            "leftPrefix": _normalize_text(payload.get("snRule", {}).get("leftPrefix"), "左件前缀", limit=16).upper(),
            "rightPrefix": _normalize_text(payload.get("snRule", {}).get("rightPrefix"), "右件前缀", limit=16).upper(),
            "sideBy": _normalize_text(payload.get("snRule", {}).get("sideBy"), "件别规则", limit=200),
        },
        "sourceFiles": payload.get("sourceFiles") or [],
        "specs": _normalize_rows(payload.get("specs"), ["label", "value"], "规格参数"),
        "functions": _normalize_rows(payload.get("functions"), ["title", "description"], "功能说明"),
        "scenarios": _normalize_rows(payload.get("scenarios"), ["title", "description"], "使用场景"),
        "sides": _normalize_sides(payload.get("sides")),
        "relatedStations": relation_items.normalize_items(payload.get("relatedStations")),
        "relatedEquipment": relation_items.normalize_items(payload.get("relatedEquipment")),
        "relatedPersons": relation_items.normalize_items(payload.get("relatedPersons")),
    }
    if product["snRule"]["length"] not in range(4, 65):
        raise ValueError("SN 长度必须在 4-64 之间")
    if not isinstance(product["sourceFiles"], list):
        raise ValueError("来源文件必须是数组")
    product["sourceFiles"] = [_normalize_text(x, "来源文件", limit=180) for x in product["sourceFiles"]]
    all_sns = _product_sns(product)
    if len(all_sns) != len(set(all_sns)):
        raise ValueError("同一产品的 SN 不能重复")
    for side in product["sides"]:
        side["count"] = len(side["sns"])
        side["firstSn"] = side["sns"][0] if side["sns"] else ""
        side["lastSn"] = side["sns"][-1] if side["sns"] else ""
    return product


def create_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    def action(config):
        product = _normalize_product(payload)
        if any(str(p.get("code", "")).upper() == product["code"] for p in config.get("products", [])):
            raise ValueError("产品编码已存在：" + product["code"])
        _ensure_unique(config, product["code"], _product_sns(product))
        config.setdefault("products", []).append(product)
        return dict(product, snRows=product_sn_rows(product))
    return _mutate(action)


def create_products_batch(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(payloads, list) or not payloads:
        raise ValueError("批量产品不能为空")
    if len(payloads) > 100:
        raise ValueError("单次最多创建 100 个产品")
    def action(config):
        products = config.setdefault("products", [])
        existing = {str(p.get("code", "")).upper() for p in products}
        batch: List[Dict[str, Any]] = []
        batch_codes: set[str] = set()
        for payload in payloads:
            product = _normalize_product(payload)
            if product["code"] in existing or product["code"] in batch_codes:
                raise ValueError("产品编码已存在：" + product["code"])
            batch_codes.add(product["code"])
            batch.append(product)
        for product in batch:
            _ensure_unique(config, product["code"], _product_sns(product))
        products.extend(batch)
        return [dict(p, snRows=product_sn_rows(p)) for p in batch]
    return _mutate(action)


def update_product(code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    code = _normalize_code(code)
    def action(config):
        products = config.get("products", [])
        index = next((i for i, p in enumerate(products) if str(p.get("code", "")).upper() == code), -1)
        if index < 0:
            raise ValueError("产品资料不存在")
        product = _normalize_product(payload, code)
        _ensure_unique(config, code, _product_sns(product))
        products[index] = product
        return dict(product, snRows=product_sn_rows(product))
    return _mutate(action)


def delete_product(code: str) -> bool:
    code = _normalize_code(code)
    def action(config):
        before = len(config.get("products", []))
        config["products"] = [p for p in config.get("products", []) if str(p.get("code", "")).upper() != code]
        return len(config["products"]) < before
    return _mutate(action)


def _next_simple_code(products: List[Dict[str, Any]]) -> str:
    numbers = []
    for product in products:
        match = re.fullmatch(r"P(\d+)", str(product.get("code", "")).strip().upper())
        if match:
            numbers.append(int(match.group(1)))
    index = 1
    while index in numbers:
        index += 1
    return f"P{index:04d}"


def ensure_product_profile(code: str, name: str) -> Dict[str, Any]:
    """数据库已有该产品但总表缺资料时，按名称补建资料结构（含 SN 清单）。"""
    code = _normalize_code(code)
    def action(config):
        products = config.setdefault("products", [])
        existing = next((p for p in products if str(p.get("code", "")).upper() == code), None)
        if existing:
            return dict(existing, snRows=product_sn_rows(existing))
        product = _normalize_product({
            "code": code,
            "name": str(name or code),
            "family": "",
            "description": "",
            "batchDate": "",
            "sourceFiles": [],
            "snRule": {"length": 16, "leftPrefix": "", "rightPrefix": "", "sideBy": "统一 SN 清单"},
            "specs": [], "functions": [], "scenarios": [],
            "sides": [{"key": "sn", "name": "SN 清单", "prefix": "", "fileName": "", "sns": []}],
        })
        products.append(product)
        return dict(product, snRows=[])
    return _mutate(action)


def create_simple_product(name: str) -> Dict[str, Any]:
    def action(config):
        products = config.setdefault("products", [])
        payload = {
            "code": _next_simple_code(products),
            "name": name,
            "family": "",
            "description": "",
            "batchDate": "",
            "sourceFiles": [],
            "snRule": {"length": 16, "leftPrefix": "", "rightPrefix": "", "sideBy": "统一 SN 清单"},
            "specs": [], "functions": [], "scenarios": [],
            "sides": [{"key": "sn", "name": "SN 清单", "prefix": "", "fileName": "", "sns": []}],
        }
        product = _normalize_product(payload)
        products.append(product)
        return dict(product, snRows=[])
    return _mutate(action)


def rename_simple_product(code: str, name: str) -> Dict[str, Any]:
    code = _normalize_code(code)
    def action(config):
        product = _find_product_in(config, code)
        product["name"] = _normalize_text(name, "产品名称", True, 128)
        return dict(product, snRows=product_sn_rows(product))
    return _mutate(action)


def import_simple_sns(code: str, sns: List[str]) -> Dict[str, Any]:
    code = _normalize_code(code)
    def action(config):
        product = _find_product_in(config, code)
        sides = product.setdefault("sides", [])
        side = next((s for s in sides if s.get("key") == "sn"), None)
        if not side:
            side = {"key": "sn", "name": "SN 清单", "prefix": "", "fileName": "", "sns": []}
            sides.append(side)
        existing = set(_product_sns(product))
        created: List[str] = []
        skipped: List[Dict[str, str]] = []
        for raw in sns or []:
            value = str(raw or "").strip().upper()
            if not SN_RE.fullmatch(value):
                skipped.append({"sn": value, "reason": "SN 必须为 16 位大写字母或数字"})
                continue
            if value in existing:
                skipped.append({"sn": value, "reason": "SN 已存在"})
                continue
            existing.add(value)
            created.append(value)
        side.setdefault("sns", []).extend(created)
        _recalc_side(side)
        return {
            **dict(product, snRows=product_sn_rows(product)),
            "createdCount": len(created),
            "skippedCount": len(skipped),
            "skipped": skipped,
        }
    return _mutate(action)


def _find_product_in(config: Dict[str, Any], code: str) -> Dict[str, Any]:
    product = next((p for p in config.get("products", []) if str(p.get("code", "")).upper() == code), None)
    if not product:
        raise ValueError("产品资料不存在")
    return product


def _recalc_side(side: Dict[str, Any]) -> None:
    side["count"] = len(side.get("sns") or [])
    side["firstSn"] = side["sns"][0] if side.get("sns") else ""
    side["lastSn"] = side["sns"][-1] if side.get("sns") else ""


def add_sns(code: str, sns: List[str], side_key: str = "") -> Dict[str, Any]:
    code = _normalize_code(code)
    def action(config):
        product = _find_product_in(config, code)
        values = [_normalize_sn(sn) for sn in (sns or [])]
        if not values:
            raise ValueError("请填写 SN")
        sides = product.get("sides") or []
        side = next((s for s in sides if s.get("key") == side_key), None) if side_key else None
        if not side and side_key:
            raise ValueError("件别不存在")
        if not side:
            side = next((s for s in sides if s.get("key") == "sn"), None) or (sides[0] if sides else None)
        if not side:
            raise ValueError("产品尚未建立 SN 清单结构")
        existing = set(_product_sns(product))
        for sn in values:
            if sn in existing:
                raise ValueError("SN 已存在：" + sn)
            existing.add(sn)
        _ensure_unique(config, code, values)
        side.setdefault("sns", []).extend(values)
        _recalc_side(side)
        return dict(product, snRows=product_sn_rows(product))
    return _mutate(action)


def update_sn(code: str, old_sn: str, new_sn: str, side_key: str = "") -> Dict[str, Any]:
    code = _normalize_code(code)
    old = _normalize_sn(old_sn)
    new = _normalize_sn(new_sn)
    def action(config):
        product = _find_product_in(config, code)
        source = None
        for side in product.get("sides", []):
            if old in (side.get("sns") or []):
                source = side
                break
        if not source:
            raise ValueError("SN 不存在：" + old)
        target = source
        if side_key:
            target = next((s for s in product.get("sides", []) if s.get("key") == side_key), None)
            if not target:
                raise ValueError("件别不存在")
        source["sns"] = [sn for sn in source.get("sns", []) if sn != old]
        existing = set(_product_sns(product))
        if new in existing:
            raise ValueError("SN 已存在：" + new)
        _ensure_unique(config, code, [new])
        target.setdefault("sns", []).append(new)
        _recalc_side(source)
        if target is not source:
            _recalc_side(target)
        return dict(product, snRows=product_sn_rows(product))
    return _mutate(action)


def delete_sn(code: str, sn: str) -> Dict[str, Any]:
    code = _normalize_code(code)
    value = _normalize_sn(sn)
    def action(config):
        product = _find_product_in(config, code)
        found = False
        for side in product.get("sides", []):
            if value in (side.get("sns") or []):
                side["sns"] = [item for item in side["sns"] if item != value]
                _recalc_side(side)
                found = True
                break
        if not found:
            raise ValueError("SN 不存在：" + value)
        return dict(product, snRows=product_sn_rows(product))
    return _mutate(action)


def delete_sns(code: str, sns: List[str]) -> Dict[str, Any]:
    """批量删除当前产品下的 SN，返回删除和未找到清单。"""
    code = _normalize_code(code)
    values = [_normalize_sn(sn) for sn in (sns or [])]
    if not values:
        raise ValueError("请选择要删除的 SN")
    wanted = set(values)
    removed: List[str] = []
    missing: List[str] = []
    def action(config):
        product = _find_product_in(config, code)
        found: set[str] = set()
        for side in product.get("sides", []):
            before = side.get("sns") or []
            side["sns"] = [item for item in before if str(item).strip().upper() not in wanted]
            found.update(str(item).strip().upper() for item in before if item not in side["sns"])
            _recalc_side(side)
        removed.extend(item for item in values if item in found)
        missing.extend(item for item in dict.fromkeys(values) if item not in found)
        return dict(product, snRows=product_sn_rows(product))
    product = _mutate(action)
    return {
        "product": product,
        "removed": list(dict.fromkeys(removed)),
        "removedCount": len(set(removed)),
        "missing": missing,
    }
