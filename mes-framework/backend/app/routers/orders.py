from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, services
from ..schemas import OrderIn, OrderOut, RecordIn

router = APIRouter(prefix="/api", tags=["生产订单与工序"])


@router.get("/orders", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db)):
    return db.query(models.WorkOrder).order_by(models.WorkOrder.id.desc()).all()


@router.post("/orders", response_model=OrderOut)
def create_order(payload: OrderIn, db: Session = Depends(get_db)):
    try:
        return services.create_order(db, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(models.WorkOrder, order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    return order


@router.post("/orders/{order_id}/release", response_model=OrderOut)
def release_order(order_id: int, db: Session = Depends(get_db)):
    try:
        return services.release_order(db, order_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/orders/{order_id}/report")
def report_production(order_id: int, payload: RecordIn, db: Session = Depends(get_db)):
    try:
        result = services.report_production(db, order_id, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "ok": True,
        "transition": result["transition"],
        "order": OrderOut.model_validate(result["order"]).model_dump(mode="json"),
        "record": result["record"].id,
    }


@router.get("/operations")
def list_operations(db: Session = Depends(get_db)):
    rows = db.query(models.WorkOrderOperation, models.WorkOrder.order_no).join(
        models.WorkOrder, models.WorkOrderOperation.work_order_id == models.WorkOrder.id
    ).order_by(models.WorkOrderOperation.id).all()
    return [
        {
            "id": op.id, "work_order_id": op.work_order_id, "order_no": order_no,
            "seq": op.seq, "name": op.name, "status": op.status,
            "plan_qty": op.plan_qty, "good_qty": op.good_qty, "bad_qty": op.bad_qty,
            "equipment_id": op.equipment_id, "started_at": op.started_at, "finished_at": op.finished_at,
        }
        for op, order_no in rows
    ]
