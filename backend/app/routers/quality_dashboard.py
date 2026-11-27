"""质量看板：只读汇总 WIP、良率、不良柏拉图和过程能力趋势。"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import NormalDist
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, deps, models, process_design_store

router = APIRouter(
    prefix="/api/quality-dashboard",
    tags=["质量看板"],
    dependencies=[Depends(auth.current_account)],
)

get_db = deps.get_db

STATE_LABELS = {
    "pending": "待生产",
    "passed": "已通过",
    "failed": "不合格",
    "rework": "返修中",
    "station_done": "站点完成",
    "packed": "已包装",
}
STATE_ORDER = ["pending", "passed", "station_done", "rework", "failed", "packed"]


def _require_view(db: Session, account: models.Account) -> str:
    if account.role == "admin":
        return account.username
    codes = {row.perm_code for row in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if "dashboard:view" not in codes:
        raise HTTPException(403, "当前账号无看板查看权限")
    return account.username


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _rate(part: int, total: int) -> float:
    return _round(part * 100 / total) if total else 0.0


def _cpk_from_yield(yield_rate: float) -> float:
    """按一次通过率折算过程能力指数；仅作趋势观察，不替代测量数据 Cpk。"""
    value = min(max(yield_rate / 100, 0.001), 0.999)
    z = NormalDist().inv_cdf(value)
    return _round(max(0.0, min(2.5, (z + 1.5) / 3)))


def _cpk_level(cpk: float, has_data: bool) -> str:
    if not has_data:
        return "暂无数据"
    if cpk >= 1.33:
        return "达标"
    if cpk >= 1.0:
        return "需关注"
    return "不足"


def _fail_code_names() -> Dict[str, str]:
    names: Dict[str, str] = {}
    try:
        config = process_design_store.load_config()
    except Exception:
        return names
    for station in config.get("stations", []):
        for item in station.get("failCodes", []):
            code = str(item.get("code") or "").strip().upper()
            if code:
                names[code] = str(item.get("name") or code)
    return names


def _wip_summary(units: List[models.Unit]) -> Dict[str, Any]:
    counts = Counter(str(row.state or "pending").lower() for row in units)
    total = len(units)
    wip = sum(count for state, count in counts.items() if state != "packed")
    statuses = []
    for state in STATE_ORDER:
        count = counts.get(state, 0)
        if state == "packed" and count == 0:
            continue
        statuses.append({
            "key": state,
            "name": STATE_LABELS.get(state, state),
            "count": count,
            "ratio": _rate(count, total),
        })
    for state, count in sorted(counts.items()):
        if state in STATE_ORDER:
            continue
        statuses.append({
            "key": state,
            "name": STATE_LABELS.get(state, state),
            "count": count,
            "ratio": _rate(count, total),
        })
    return {"total": wip, "unitTotal": total, "statuses": statuses}


def _quality_summary(records: List[models.StationRecord]) -> Dict[str, Any]:
    total = len(records)
    passed = sum(1 for row in records if str(row.result or "").lower() == "pass")
    failed = sum(1 for row in records if str(row.result or "").lower() == "fail")
    reworked = sum(1 for row in records if str(row.result or "").lower() == "rework")
    good_rate = _rate(passed, total)
    defect_rate = _rate(failed + reworked, total)
    cpk = _cpk_from_yield(good_rate) if total else 0.0
    return {
        "checks": total,
        "passed": passed,
        "failed": failed,
        "reworked": reworked,
        "goodRate": good_rate,
        "defectRate": defect_rate,
        "cpk": cpk,
        "cpkTarget": 1.33,
        "cpkLevel": _cpk_level(cpk, bool(total)),
        "hasData": bool(total),
        "recordedUnits": len({int(row.unit_id) for row in records if row.unit_id}),
    }


def _defect_summary(records: List[models.StationRecord]) -> Dict[str, Any]:
    defects = [row for row in records if str(row.result or "").lower() in {"fail", "rework"}]
    total = len(defects)
    names = _fail_code_names()
    grouped: Dict[str, Dict[str, Any]] = {}
    station_counts: Counter = Counter()
    for row in defects:
        code = str(row.fail_code or "").strip().upper() or "未分类"
        item = grouped.setdefault(code, {"code": code, "name": names.get(code, code), "count": 0, "stations": Counter()})
        item["count"] += 1
        item["stations"][str(row.station or "未分配")] += 1
        station_counts[str(row.station or "未分配")] += 1
    ranked = sorted(grouped.values(), key=lambda item: (-item["count"], item["code"]))
    cumulative = 0
    items = []
    for index, item in enumerate(ranked, start=1):
        cumulative += item["count"]
        items.append({
            "rank": index,
            "code": item["code"],
            "name": item["name"],
            "count": item["count"],
            "ratio": _rate(item["count"], total),
            "cumulativeRatio": _rate(cumulative, total),
        })
    station_items = [
        {"name": name, "count": count, "ratio": _rate(count, total)}
        for name, count in sorted(station_counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    return {"total": total, "items": items, "byStation": station_items}


def _cpk_trend(records: List[models.StationRecord]) -> List[Dict[str, Any]]:
    today = datetime.utcnow().date()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    buckets: Dict[Any, Dict[str, int]] = {day: {"pass": 0, "fail": 0, "rework": 0} for day in days}
    for row in records:
        created = row.created_at.date() if row.created_at else None
        if created not in buckets:
            continue
        result = str(row.result or "").lower()
        if result in buckets[created]:
            buckets[created][result] += 1
    trend = []
    for day in days:
        counts = buckets[day]
        checks = sum(counts.values())
        good_rate = _rate(counts["pass"], checks)
        trend.append({
            "date": day.isoformat(),
            "label": day.strftime("%m-%d"),
            "checks": checks,
            "passed": counts["pass"],
            "goodRate": good_rate,
            "cpk": _cpk_from_yield(good_rate) if checks else 0.0,
            "hasData": bool(checks),
        })
    return trend


@router.get("/summary")
def quality_summary(
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_view(db, account)
    units = db.query(models.Unit).all()
    records = db.query(models.StationRecord).all()
    generated_at = datetime.utcnow()
    return {
        "generatedAt": generated_at.isoformat(timespec="seconds"),
        "wip": _wip_summary(units),
        "quality": _quality_summary(records),
        "defects": _defect_summary(records),
        "trend": _cpk_trend(records),
        "note": "CPK 按过站一次通过率折算，仅用于趋势观察；不替代测量数据计算的 Cpk。",
    }
