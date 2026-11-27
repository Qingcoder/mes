from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..schemas import RecordOut

router = APIRouter(prefix="/api", tags=["生产数据采集"])


@router.get("/records", response_model=list[RecordOut])
def list_records(
    order_id: Optional[int] = Query(None),
    operation_id: Optional[int] = Query(None),
    equipment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.ProductionRecord)
    if order_id is not None:
        query = query.filter(models.ProductionRecord.work_order_id == order_id)
    if operation_id is not None:
        query = query.filter(models.ProductionRecord.operation_id == operation_id)
    if equipment_id is not None:
        query = query.filter(models.ProductionRecord.equipment_id == equipment_id)
    return query.order_by(models.ProductionRecord.recorded_at.desc()).limit(300).all()
