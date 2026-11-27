"""跨模块关联对象的统一字段与归一化。"""
from typing import Any, Dict, Iterable, List

RELATION_FIELDS = ("relatedProducts", "relatedEquipment", "relatedPersons", "relatedStations")


def normalize_items(value: Any, limit: int = 128) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    seen: set[str] = set()
    values: Iterable[Any] = value if isinstance(value, list) else []
    for item in values:
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
            name = str(item.get("name") or code).strip()
        else:
            code = str(item or "").strip()
            name = code
        if not code or code in seen:
            continue
        seen.add(code)
        result.append({"code": code[:64], "name": name[:limit] or code[:64]})
    return result


def codes(items: Any) -> List[str]:
    return [str(item.get("code") or "") for item in normalize_items(items) if item.get("code")]


def merge_items(*groups: Any, limit: int = 128) -> List[Dict[str, str]]:
    merged: List[Dict[str, str]] = []
    index: Dict[str, int] = {}
    for group in groups:
        for item in normalize_items(group, limit=limit):
            code = item["code"]
            if code in index:
                if not merged[index[code]].get("name") and item.get("name"):
                    merged[index[code]]["name"] = item["name"]
                continue
            index[code] = len(merged)
            merged.append(item)
    return merged


def upsert_code(items: Any, code: str, name: str = "", limit: int = 128) -> List[Dict[str, str]]:
    code = str(code or "").strip()
    if not code:
        return normalize_items(items, limit=limit)
    return merge_items(items, [{"code": code, "name": name or code}], limit=limit)


def remove_code(items: Any, code: str, limit: int = 128) -> List[Dict[str, str]]:
    key = str(code or "").strip()
    return [item for item in normalize_items(items, limit=limit) if item["code"] != key]
