"""SN 库数据层。

SN 库是产品资料总表的只读汇总视图：
产品在产品资料中导入 SN 后，本接口自动从 product_profiles.json 汇总，
不再独立保存 SN 主数据，也不与产品资料里的 SN 分表维护。
"""
from typing import Any, Dict, List, Optional

from . import product_profiles_store

WRITE_DENIED = "SN 库由产品资料总表自动汇总，请在产品资料中导入和维护 SN"


def _text(value: Any) -> str:
    return str(value or "").strip()


def list_records(keyword: str = "", product: str = "") -> List[Dict[str, Any]]:
    rows = product_profiles_store.sn_master_records()
    key = _text(keyword).lower()
    prod = _text(product).lower()
    if key:
        rows = [row for row in rows if any(
            key in _text(row.get(field)).lower()
            for field in ("sn", "product", "productCode", "sideName", "sourceFile", "remark")
        )]
    if prod:
        rows = [row for row in rows if prod in _text(row.get("product")).lower()]
    return sorted(rows, key=lambda row: _text(row.get("sn")))


def find_record(record_id: str) -> Optional[Dict[str, Any]]:
    key = _text(record_id)
    return next((row for row in product_profiles_store.sn_master_records() if _text(row.get("id")) == key), None)


def summary() -> Dict[str, Any]:
    rows = product_profiles_store.sn_master_records()
    duplicates = product_profiles_store.sn_master_duplicates()
    products = sorted({_text(row.get("product")) for row in rows if _text(row.get("product"))})
    return {
        "total": len(rows),
        "products": products,
        "duplicateGroups": len(duplicates),
        "duplicateRemoved": sum(int(item.get("removed") or 0) for item in duplicates),
        "duplicates": duplicates,
    }


def create_record(payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    raise ValueError(WRITE_DENIED)


def update_record(record_id: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    raise ValueError(WRITE_DENIED)


def delete_record(record_id: str) -> Dict[str, Any]:
    raise ValueError(WRITE_DENIED)
