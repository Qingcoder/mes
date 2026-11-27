from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, services
from ..schemas import EquipmentIn, EquipmentOut, EquipmentStatusIn, EquipmentEventOut

router = APIRouter(prefix="/api", tags=["设备监控"])


@router.get("/equipment", response_model=list[EquipmentOut])
def list_equipment(db: Session = Depends(get_db)):
    return db.query(models.Equipment).order_by(models.Equipment.id).all()


@router.post("/equipment", response_model=EquipmentOut)
def create_equipment(payload: EquipmentIn, db: Session = Depends(get_db)):
    if db.query(models.Equipment).filter_by(code=payload.code).first():
        raise HTTPException(400, "设备编码已存在")
    item = models.Equipment(code=payload.code.strip(), name=payload.name.strip(), status=payload.status)
    db.add(item)
    db.flush()
    db.add(models.EquipmentEvent(equipment_id=item.id, from_status="", to_status=payload.status, reason="设备建档"))
    db.commit()
    db.refresh(item)
    return item


@router.post("/equipment/{equipment_id}/status", response_model=EquipmentOut)
def change_status(equipment_id: int, payload: EquipmentStatusIn, db: Session = Depends(get_db)):
    try:
        return services.set_equipment_status(db, equipment_id, payload.status, payload.reason)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/equipment/{equipment_id}/events", response_model=list[EquipmentEventOut])
def equipment_events(equipment_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Equipment, equipment_id):
        raise HTTPException(404, "设备不存在")
    return db.query(models.EquipmentEvent).filter_by(equipment_id=equipment_id).order_by(
        models.EquipmentEvent.at.desc()
    ).limit(100).all()
