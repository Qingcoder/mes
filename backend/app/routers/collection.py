"""扫码事件采集、清洗入库与产品维度报表。

设计约束：
- 不新增数据库表，复用 station_records / units / wos / audit_logs。
- audit_logs 作为原始事件与幂等账本：action=scan.collect.*，target=event_id。
- station_records 作为清洗后的事实数据；报表由关联查询实时聚合。
"""
import csv
import hashlib
import io
import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .. import auth, deps, models
from ..permission_guard import write_audit

router = APIRouter(prefix="/api", tags=["扫码采集与报表"])
logger = logging.getLogger("mes.collection")

SN_RE = re.compile(r"^[A-Z0-9]{16}$")
MAX_RETRY = 3
_COLLECT_LOCK = threading.Lock()


class ScanEventIn(BaseModel):
    event_id: Optional[str] = None
    sn: str
    station: str
    result: str
    fail_code: Optional[str] = None
    operator: Optional[str] = None
    source: str = "scanner"


class ScanEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ok: bool
    status: str
    event_id: str
    sn: str
    wo_no: str = ""
    product: str = ""
    station: str
    result: str
    state: str = ""
    msg: str


class ProductReportItem(BaseModel):
    key: str
    product: str
    station: Optional[str] = None
    day: Optional[str] = None
    total_events: int
    unique_sn: int
    pass_count: int
    fail_count: int
    rework_count: int
    first_pass_count: int
    fpy: float
    fail_rate: float
    packed_count: int
    last_event_at: Optional[datetime] = None


class ProductReportOut(BaseModel):
    generated_at: datetime
    group_by: str
    total_groups: int
    items: List[ProductReportItem]


class CollectionHealthOut(BaseModel):
    accepted_24h: int
    duplicates_24h: int
    rejected_24h: int
    failed_24h: int
    last_event_at: Optional[datetime] = None
    note: str


def actor_dep(
    account: models.Account = Depends(auth.current_account),
    x_operator: str = Header(default=""),
) -> str:
    """审计身份以登录账号为准，X-Operator 仅保留兼容，不作为身份依据。"""
    return account.username


get_db = deps.get_db


def _event_id(body: ScanEventIn) -> str:
    if body.event_id and body.event_id.strip():
        return body.event_id.strip()[:120]
    raw = "|".join([
        body.sn.strip().upper(), body.station.strip(), body.result.strip().lower(),
        (body.fail_code or "").strip().upper(), (body.operator or "").strip(), body.source,
    ])
    return "evt_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _clean_body(body: ScanEventIn):
    return {
        "sn": (body.sn or "").strip().upper(),
        "station": (body.station or "").strip(),
        "result": (body.result or "").strip().lower(),
        "fail_code": (body.fail_code or "").strip().upper() or None,
        "operator": (body.operator or "").strip() or "system",
        "source": (body.source or "scanner").strip()[:32],
    }


def _validate(data: dict) -> None:
    if not SN_RE.fullmatch(data["sn"]):
        raise ValueError("SN 必须为 16 位大写字母或数字")
    if not data["station"]:
        raise ValueError("站点不能为空")
    if data["result"] not in ("pass", "fail"):
        raise ValueError("result 只能是 pass 或 fail")
    if data["result"] == "fail" and not data["fail_code"]:
        raise ValueError("不良时必须提供 fail_code")


def _find_accepted(db: Session, event_id: str):
    row = db.query(models.AuditLog).filter(
        models.AuditLog.action == "scan.collect.accepted",
        models.AuditLog.target == event_id,
    ).first()
    if not row:
        return None
    try:
        return json.loads((row.detail or "{}").split("RESULT=", 1)[0])
    except Exception:
        return {"event_id": event_id}


def _apply_station(db: Session, data: dict):
    u = db.query(models.Unit).filter_by(sn=data["sn"]).first()
    if not u:
        raise ValueError("SN 不存在")
    wo = db.get(models.WorkOrder, u.wo_id)
    if not wo:
        raise ValueError("SN 所属工单不存在")
    stations = list(wo.stations or [])
    if data["station"] not in stations:
        raise ValueError(f"站点 {data['station']} 不在本工单序列中")
    idx = stations.index(data["station"])
    done = {r.station for r in u.records if r.result == "pass"}
    for s in stations[:idx]:
        if s not in done:
            raise ValueError(f"不能跳站：请先完成 {s}")
    if data["station"] in done:
        return u, wo, "skip", "本站已通过（幂等跳过）"

    u.current_station = data["station"]
    if data["result"] == "pass":
        u.state = "station_done" if idx == len(stations) - 1 else "passed"
        u.fail_code = None
        msg = "通过 · 已流转"
    else:
        u.state = "failed"
        u.fail_code = data["fail_code"]
        msg = "不良 · 已记录"

    db.add(models.StationRecord(
        unit_id=u.id, station=data["station"], result=data["result"],
        fail_code=data["fail_code"], source_type=f"collect:{data['source']}",
        operator=data["operator"],
    ))
    return u, wo, "applied", msg


def _write_count(db: Session, action: str, since: datetime) -> int:
    return db.query(models.AuditLog).filter(
        models.AuditLog.action == action,
        models.AuditLog.ts >= since,
    ).count()


@router.post("/collection/scan", response_model=ScanEventOut)
def collect_scan(
    body: ScanEventIn,
    actor: str = Depends(actor_dep),
    db: Session = Depends(get_db),
):
    """采集单条扫码事件；同 event_id 重复提交直接返回首次结果。"""
    event_id = _event_id(body)
    data = _clean_body(body)
    raw = json.dumps({**data, "event_id": event_id}, ensure_ascii=False, separators=(",", ":"))

    try:
        _validate(data)
    except ValueError as exc:
        detail = f"RAW={raw[:300]}; reason={exc}"
        write_audit(db, actor, "scan.collect.rejected", event_id, detail, commit=True)
        logger.warning("scan rejected event=%s reason=%s", event_id, exc)
        raise HTTPException(400, str(exc))

    with _COLLECT_LOCK:
        for attempt in range(MAX_RETRY):
            try:
                db.rollback()
                duplicate_out = None
                accepted_out = None
                with db.begin():
                    existing = _find_accepted(db, event_id)
                    if existing:
                        write_audit(db, actor, "scan.collect.duplicate", event_id, f"event_id={event_id}", commit=False)
                        duplicate_out = ScanEventOut(
                            ok=True, status="duplicate", event_id=event_id,
                            sn=existing.get("sn", data["sn"]), wo_no=existing.get("wo_no", ""),
                            product=existing.get("product", ""), station=existing.get("station", data["station"]),
                            result=existing.get("result", data["result"]), state=existing.get("state", ""),
                            msg="重复事件（幂等返回）",
                        )
                    else:
                        u, wo, apply_status, msg = _apply_station(db, data)
                        result_payload = {
                            "event_id": event_id, "sn": data["sn"], "wo_no": wo.wo_no,
                            "product": wo.product, "station": data["station"],
                            "result": data["result"], "state": u.state,
                        }
                        write_audit(db, actor, "scan.collect.raw", event_id, raw[:480], commit=False)
                        write_audit(
                            db, actor, "scan.collect.accepted", event_id,
                            json.dumps(result_payload, ensure_ascii=False, separators=(",", ":"))[:512],
                            commit=False,
                        )
                        accepted_out = ScanEventOut(
                            ok=True, status="accepted", **result_payload, msg=msg,
                        )
                        logger.info("scan accepted event=%s sn=%s status=%s", event_id, data["sn"], apply_status)
                if duplicate_out:
                    return duplicate_out
                if accepted_out:
                    return accepted_out

            except ValueError as exc:
                db.rollback()
                write_audit(db, actor, "scan.collect.rejected", event_id, f"RAW={raw[:300]}; reason={exc}", commit=True)
                logger.warning("scan rejected event=%s reason=%s", event_id, exc)
                raise HTTPException(400, str(exc))
            except OperationalError as exc:
                db.rollback()
                logger.warning("database locked, retry event=%s attempt=%s err=%s", event_id, attempt + 1, exc)
                if attempt == MAX_RETRY - 1:
                    write_audit(db, actor, "scan.collect.failed", event_id, f"RAW={raw[:300]}; reason=db_locked", commit=True)
                    raise HTTPException(503, "采集服务繁忙，请使用同一 event_id 重试")
                time.sleep(0.05 * (attempt + 1))

        raise HTTPException(503, "采集失败，请使用同一 event_id 重试")


def _report_rows(
    db: Session,
    product: Optional[str],
    station: Optional[str],
    result: Optional[str],
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
):
    q = db.query(
        models.StationRecord, models.Unit, models.WorkOrder,
    ).join(models.Unit, models.StationRecord.unit_id == models.Unit.id) \
     .join(models.WorkOrder, models.Unit.wo_id == models.WorkOrder.id)
    if product:
        q = q.filter(models.WorkOrder.product.like(f"%{product}%"))
    if station:
        q = q.filter(models.StationRecord.station == station)
    if result:
        q = q.filter(models.StationRecord.result == result)
    if from_ts:
        q = q.filter(models.StationRecord.created_at >= from_ts)
    if to_ts:
        q = q.filter(models.StationRecord.created_at <= to_ts)
    return q.order_by(models.StationRecord.created_at.asc(), models.StationRecord.id.asc()).all()


def _aggregate(rows, group_by: str) -> List[ProductReportItem]:
    groups = {}
    first_by_sn = {}
    for rec, unit, wo in rows:
        key = wo.product
        st = None
        day = None
        if group_by == "product_station":
            key = f"{wo.product}|{rec.station}"
            st = rec.station
        elif group_by == "product_day":
            day = rec.created_at.strftime("%Y-%m-%d") if rec.created_at else ""
            key = f"{wo.product}|{day}"
        g = groups.setdefault(key, {
            "product": wo.product, "station": st, "day": day,
            "events": 0, "sns": set(), "pass": 0, "fail": 0, "rework": 0,
            "packed": set(), "last": None,
        })
        g["events"] += 1
        g["sns"].add(unit.sn)
        if rec.result == "pass":
            g["pass"] += 1
        elif rec.result == "fail":
            g["fail"] += 1
        elif rec.result == "rework":
            g["rework"] += 1
        if unit.state == "packed":
            g["packed"].add(unit.sn)
        g["last"] = rec.created_at
        if unit.sn not in first_by_sn:
            first_by_sn[unit.sn] = (rec.result, key)

    out = []
    for key, g in groups.items():
        uniq = len(g["sns"])
        first_pass = sum(1 for res, gkey in first_by_sn.values() if gkey == key and res == "pass")
        out.append(ProductReportItem(
            key=key, product=g["product"], station=g["station"], day=g["day"],
            total_events=g["events"], unique_sn=uniq,
            pass_count=g["pass"], fail_count=g["fail"], rework_count=g["rework"],
            first_pass_count=first_pass,
            fpy=round(first_pass * 100 / uniq, 2) if uniq else 0,
            fail_rate=round(g["fail"] * 100 / g["events"], 2) if g["events"] else 0,
            packed_count=len(g["packed"]), last_event_at=g["last"],
        ))
    return out


@router.get("/reports/products", response_model=ProductReportOut)
def product_report(
    product: Optional[str] = None,
    station: Optional[str] = None,
    result: Optional[str] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    group_by: str = Query("product", pattern="^(product|product_station|product_day)$"),
    db: Session = Depends(get_db),
    actor: str = Depends(actor_dep),
):
    rows = _report_rows(db, product, station, result, from_ts, to_ts)
    items = _aggregate(rows, group_by)
    write_audit(db, actor, "report.product.query", group_by,
                f"groups={len(items)}; rows={len(rows)}; product={product or ''}", commit=True)
    return ProductReportOut(generated_at=datetime.utcnow(), group_by=group_by,
                            total_groups=len(items), items=items)


@router.get("/reports/products/export")
def product_report_export(
    product: Optional[str] = None,
    station: Optional[str] = None,
    result: Optional[str] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    group_by: str = Query("product", pattern="^(product|product_station|product_day)$"),
    db: Session = Depends(get_db),
    actor: str = Depends(actor_dep),
):
    rows = _report_rows(db, product, station, result, from_ts, to_ts)
    items = _aggregate(rows, group_by)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["维度", "产品", "站点", "日期", "事件数", "唯一SN", "通过", "不良", "返修",
                     "首次通过", "直通率FPY(%)", "不良率(%)", "已装箱", "最后事件时间"])
    for it in items:
        writer.writerow([
            it.key, it.product, it.station or "", it.day or "", it.total_events, it.unique_sn,
            it.pass_count, it.fail_count, it.rework_count, it.first_pass_count, it.fpy,
            it.fail_rate, it.packed_count,
            it.last_event_at.strftime("%Y-%m-%d %H:%M:%S") if it.last_event_at else "",
        ])
    write_audit(db, actor, "report.product.export", group_by,
                f"groups={len(items)}; rows={len(rows)}; product={product or ''}", commit=True)
    filename = "product_report_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".csv"
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/collection/health", response_model=CollectionHealthOut)
def collection_health(db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(hours=24)
    last = db.query(models.AuditLog).filter(
        models.AuditLog.action.like("scan.collect.%")
    ).order_by(models.AuditLog.ts.desc()).first()
    return CollectionHealthOut(
        accepted_24h=_write_count(db, "scan.collect.accepted", since),
        duplicates_24h=_write_count(db, "scan.collect.duplicate", since),
        rejected_24h=_write_count(db, "scan.collect.rejected", since),
        failed_24h=_write_count(db, "scan.collect.failed", since),
        last_event_at=last.ts if last else None,
        note="日志账本写入 audit_logs；生产环境建议接入日志采集与告警",
    )
