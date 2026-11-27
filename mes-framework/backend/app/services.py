"""业务服务层：工单状态机、工序展开、报工联动与设备状态联动。

所有状态变更集中在此，Router 只负责参数校验与 HTTP 响应。
"""
from datetime import datetime

from sqlalchemy.orm import Session

from . import models
from .schemas import OrderIn, RecordIn

EQUIPMENT_STATUSES = {"idle", "running", "down", "maintenance"}
ORDER_ACTIVE_STATUSES = {"released", "in_progress"}


def _now():
    return datetime.utcnow()


def next_order_no(db: Session) -> str:
    prefix = "WO-" + _now().strftime("%Y%m%d") + "-"
    last = db.query(models.WorkOrder).filter(models.WorkOrder.order_no.like(prefix + "%")).order_by(models.WorkOrder.id.desc()).first()
    seq = 1
    if last:
        try:
            seq = int(last.order_no.rsplit("-", 1)[-1]) + 1
        except ValueError:
            seq = 1
    return prefix + f"{seq:03d}"


def _route_op_def(route, seq):
    for item in (route.operations or []):
        if int(item.get("sequence", 0)) == seq:
            return item
    return {}


def _set_equipment(db: Session, equipment_id, status, reason):
    if not equipment_id:
        return
    eq = db.get(models.Equipment, equipment_id)
    if not eq:
        return
    old = eq.status
    if old == status:
        return
    eq.status = status
    if status != "running":
        eq.current_order_id = None
        eq.current_operation_id = None
    db.add(models.EquipmentEvent(equipment_id=eq.id, from_status=old, to_status=status, reason=reason))


def _equipment_for_operation(db: Session, route, operation):
    code = _route_op_def(route, operation.seq).get("equipment_code")
    if not code:
        return None
    return db.query(models.Equipment).filter_by(code=code).first()


def create_order(db: Session, payload: OrderIn) -> models.WorkOrder:
    product = db.get(models.Product, payload.product_id)
    route = db.get(models.Route, payload.route_id)
    if not product:
        raise ValueError("产品不存在")
    if not route:
        raise ValueError("工艺路线不存在")
    if route.product_id != product.id:
        raise ValueError("工艺路线与产品不匹配")
    if payload.plan_qty <= 0:
        raise ValueError("计划数量必须大于 0")
    if not route.operations:
        raise ValueError("工艺路线尚未维护工序")

    order = models.WorkOrder(
        order_no=(payload.order_no or next_order_no(db)).strip(),
        product_id=product.id,
        route_id=route.id,
        plan_qty=payload.plan_qty,
        status="draft",
        current_seq=0,
    )
    db.add(order)
    db.flush()

    for item in sorted(route.operations, key=lambda x: int(x.get("sequence", 0))):
        db.add(models.WorkOrderOperation(
            work_order_id=order.id,
            seq=int(item.get("sequence", 0)),
            name=str(item.get("name", "未命名工序")),
            standard_minutes=int(item.get("standard_minutes", 0) or 0),
            status="pending",
            plan_qty=payload.plan_qty,
        ))
    db.commit()
    db.refresh(order)
    return order


def release_order(db: Session, order_id: int) -> models.WorkOrder:
    order = db.get(models.WorkOrder, order_id)
    if not order:
        raise ValueError("工单不存在")
    if order.status != "draft":
        raise ValueError("只有草稿工单可以下发")
    ops = sorted(order.operations, key=lambda o: o.seq)
    if not ops:
        raise ValueError("工单没有工序")
    first = ops[0]
    order.status = "released"
    order.released_at = _now()
    order.current_seq = first.seq
    first.status = "in_progress"
    first.started_at = _now()
    eq = _equipment_for_operation(db, order.route, first)
    if eq:
        first.equipment_id = eq.id
        eq.current_order_id = order.id
        eq.current_operation_id = first.id
        _set_equipment(db, eq.id, "running", f"工单 {order.order_no} 工序 {first.name} 开工")
    db.commit()
    db.refresh(order)
    return order


def report_production(db: Session, order_id: int, payload: RecordIn):
    order = db.get(models.WorkOrder, order_id)
    if not order:
        raise ValueError("工单不存在")
    if order.status not in ORDER_ACTIVE_STATUSES:
        raise ValueError("工单不在可报工状态")
    if payload.good_qty < 0 or payload.bad_qty < 0 or (payload.good_qty + payload.bad_qty) <= 0:
        raise ValueError("合格数/不合格数必须为非负数，且合计大于 0")

    current = next((op for op in order.operations if op.status == "in_progress"), None)
    if not current:
        raise ValueError("当前没有进行中的工序")

    equipment_id = payload.equipment_id or current.equipment_id
    record = models.ProductionRecord(
        work_order_id=order.id,
        operation_id=current.id,
        equipment_id=equipment_id,
        operator=(payload.operator or "").strip(),
        good_qty=payload.good_qty,
        bad_qty=payload.bad_qty,
        note=payload.note or "",
        recorded_at=_now(),
    )
    db.add(record)
    current.good_qty += payload.good_qty
    current.bad_qty += payload.bad_qty
    order.status = "in_progress"

    transition = None
    if current.good_qty + current.bad_qty >= current.plan_qty:
        current.status = "done"
        current.finished_at = _now()
        if current.equipment_id:
            _set_equipment(db, current.equipment_id, "idle", f"工单 {order.order_no} 工序 {current.name} 完成")
        nxt = next((op for op in sorted(order.operations, key=lambda o: o.seq) if op.status == "pending"), None)
        if nxt:
            nxt.status = "in_progress"
            nxt.started_at = _now()
            order.current_seq = nxt.seq
            eq = _equipment_for_operation(db, order.route, nxt)
            if eq:
                nxt.equipment_id = eq.id
                eq.current_order_id = order.id
                eq.current_operation_id = nxt.id
                _set_equipment(db, eq.id, "running", f"工单 {order.order_no} 工序 {nxt.name} 开工")
            transition = f"进入工序 {nxt.seq} {nxt.name}"
        else:
            order.status = "completed"
            order.completed_at = _now()
            transition = "工单完工"

    db.commit()
    db.refresh(order)
    db.refresh(record)
    return {"order": order, "record": record, "transition": transition or "继续当前工序报工"}


def set_equipment_status(db: Session, equipment_id: int, status: str, reason: str = "") -> models.Equipment:
    eq = db.get(models.Equipment, equipment_id)
    if not eq:
        raise ValueError("设备不存在")
    if status not in EQUIPMENT_STATUSES:
        raise ValueError("设备状态不合法")
    _set_equipment(db, eq.id, status, reason or "人工调整")
    db.commit()
    db.refresh(eq)
    return eq


def dashboard(db: Session) -> dict:
    orders = db.query(models.WorkOrder).all()
    ops = db.query(models.WorkOrderOperation).all()
    eqs = db.query(models.Equipment).all()
    records = db.query(models.ProductionRecord).all()

    order_status = {s: 0 for s in ["draft", "released", "in_progress", "completed", "closed"]}
    for o in orders:
        order_status[o.status] = order_status.get(o.status, 0) + 1
    op_status = {s: 0 for s in ["pending", "in_progress", "done"]}
    for op in ops:
        op_status[op.status] = op_status.get(op.status, 0) + 1
    eq_status = {s: 0 for s in ["idle", "running", "down", "maintenance"]}
    for e in eqs:
        eq_status[e.status] = eq_status.get(e.status, 0) + 1

    good = sum(r.good_qty for r in records)
    bad = sum(r.bad_qty for r in records)
    total = good + bad
    return {
        "orders": {"total": len(orders), "by_status": order_status},
        "operations": {"total": len(ops), "by_status": op_status},
        "equipment": {"total": len(eqs), "by_status": eq_status},
        "production": {
            "good_qty": good,
            "bad_qty": bad,
            "total_qty": total,
            "qualified_rate": round(good / total * 100, 2) if total else 0.0,
            "record_count": len(records),
        },
        "recent_records": sorted(records, key=lambda r: r.recorded_at or _now(), reverse=True)[:8],
    }
