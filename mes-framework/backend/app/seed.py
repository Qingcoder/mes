"""演示主数据与一个已下发的演示工单，保证首次启动即可走通闭环。"""
from sqlalchemy.orm import Session

from . import models
from .schemas import OrderIn
from .services import create_order, release_order


def seed(db: Session):
    if db.query(models.Product).count() == 0:
        db.add_all([
            models.Product(code="P-BP", name="智能遥操背包"),
            models.Product(code="P-SENSOR", name="数据采集模组"),
        ])
        db.commit()

    if db.query(models.Equipment).count() == 0:
        db.add_all([
            models.Equipment(code="EQ-ASM", name="整机组装线", status="idle"),
            models.Equipment(code="EQ-TEST", name="功能测试台", status="idle"),
            models.Equipment(code="EQ-PACK", name="包装入库机", status="idle"),
        ])
        db.commit()

    if db.query(models.Route).count() == 0:
        bp = db.query(models.Product).filter_by(code="P-BP").first()
        sensor = db.query(models.Product).filter_by(code="P-SENSOR").first()
        db.add_all([
            models.Route(
                code="R-BP", name="背包标准工艺", product_id=bp.id, version="1.0",
                operations=[
                    {"name": "整机组装", "sequence": 1, "standard_minutes": 10, "equipment_code": "EQ-ASM"},
                    {"name": "功能测试", "sequence": 2, "standard_minutes": 8, "equipment_code": "EQ-TEST"},
                    {"name": "包装入库", "sequence": 3, "standard_minutes": 5, "equipment_code": "EQ-PACK"},
                ],
            ),
            models.Route(
                code="R-SENSOR", name="模组标准工艺", product_id=sensor.id, version="1.0",
                operations=[
                    {"name": "模组装配", "sequence": 1, "standard_minutes": 6, "equipment_code": "EQ-ASM"},
                    {"name": "标定测试", "sequence": 2, "standard_minutes": 7, "equipment_code": "EQ-TEST"},
                ],
            ),
        ])
        db.commit()

    if db.query(models.WorkOrder).count() == 0:
        bp = db.query(models.Product).filter_by(code="P-BP").first()
        route = db.query(models.Route).filter_by(code="R-BP").first()
        order = create_order(db, OrderIn(product_id=bp.id, route_id=route.id, plan_qty=20, order_no="WO-DEMO-001"))
        release_order(db, order.id)
