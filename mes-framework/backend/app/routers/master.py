from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..schemas import ProductIn, ProductOut, RouteIn, RouteOut

router = APIRouter(prefix="/api", tags=["主数据"])


@router.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).order_by(models.Product.id).all()


@router.post("/products", response_model=ProductOut)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    if db.query(models.Product).filter_by(code=payload.code).first():
        raise HTTPException(400, "产品编码已存在")
    item = models.Product(code=payload.code.strip(), name=payload.name.strip())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/routes", response_model=list[RouteOut])
def list_routes(db: Session = Depends(get_db)):
    return db.query(models.Route).order_by(models.Route.id).all()


@router.post("/routes", response_model=RouteOut)
def create_route(payload: RouteIn, db: Session = Depends(get_db)):
    if not db.get(models.Product, payload.product_id):
        raise HTTPException(400, "产品不存在")
    if db.query(models.Route).filter_by(code=payload.code).first():
        raise HTTPException(400, "工艺路线编码已存在")
    item = models.Route(
        code=payload.code.strip(), name=payload.name.strip(),
        product_id=payload.product_id, version=payload.version,
        operations=sorted(payload.operations, key=lambda x: int(x.get("sequence", 0))),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
