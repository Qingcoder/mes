"""SN 替换链服务。

替换语义：同一台设备换新标，旧 SN 作废、新 SN 接续原过站记录。
- 工单 SN 总数不变（替换不增减数量）；
- 新 SN 继承旧 SN 的过站记录与状态；
- 连续多次替换形成链条，可按任一 SN 查到完整替换链。
"""
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import models

SN_RE = re.compile(r"^[A-Z0-9]{16}$")


def normalize_sn(value: Any) -> str:
    return str(value or "").strip().upper()


def valid_sn(value: Any) -> bool:
    return bool(SN_RE.fullmatch(normalize_sn(value)))


def chain_for_unit(db: Session, unit: models.Unit) -> List[Dict[str, Any]]:
    """返回该 SN 的替换链，按时间正序：最早的原 SN 到当前 SN。"""
    rows = db.query(models.SnReplacement).filter_by(unit_id=unit.id).order_by(
        models.SnReplacement.id.asc()
    ).all()
    chain: List[Dict[str, Any]] = []
    seen = set()
    origin = unit.origin_sn or unit.sn
    if origin and origin not in seen:
        chain.append({"sn": origin, "role": "origin", "station": "", "operator": "", "reason": "", "createdAt": ""})
        seen.add(origin)
    for row in rows:
        if row.old_sn in seen:
            continue
        chain.append({
            "sn": row.old_sn, "role": "replaced", "station": row.station or "",
            "operator": row.operator or "", "reason": row.reason or "",
            "createdAt": row.created_at.isoformat() + "Z" if row.created_at else "",
        })
        seen.add(row.old_sn)
    if unit.sn not in seen:
        chain.append({
            "sn": unit.sn, "role": "current", "station": unit.current_station or "",
            "operator": "", "reason": "", "createdAt": "",
        })
    return chain


def find_unit_by_sn(db: Session, sn: str) -> Optional[models.Unit]:
    """按当前 SN 或替换链中的任一 SN 找到对应设备。"""
    code = normalize_sn(sn)
    if not code:
        return None
    unit = db.query(models.Unit).filter_by(sn=code).first()
    if unit:
        return unit
    row = db.query(models.SnReplacement).filter(
        (models.SnReplacement.old_sn == code) | (models.SnReplacement.new_sn == code)
    ).order_by(models.SnReplacement.id.desc()).first()
    if row:
        return db.get(models.Unit, row.unit_id)
    origin = db.query(models.Unit).filter_by(origin_sn=code).first()
    return origin


def unit_history(db: Session, unit: models.Unit) -> List[Dict[str, Any]]:
    """设备的完整履历：过站记录 + 替换记录，按时间合并。"""
    items: List[Dict[str, Any]] = []
    for record in unit.records:
        items.append({
            "kind": "station", "station": record.station or "", "result": record.result,
            "failCode": record.fail_code or "", "operator": record.operator or "",
            "createdAt": record.created_at.isoformat() + "Z" if record.created_at else "",
        })
    for row in db.query(models.SnReplacement).filter_by(unit_id=unit.id).all():
        items.append({
            "kind": "replace", "station": row.station or "", "result": "replace",
            "failCode": "", "operator": row.operator or "",
            "oldSn": row.old_sn, "newSn": row.new_sn, "reason": row.reason or "",
            "createdAt": row.created_at.isoformat() + "Z" if row.created_at else "",
        })
    return sorted(items, key=lambda item: item.get("createdAt") or "")
