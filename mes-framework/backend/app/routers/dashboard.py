from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import dashboard as build_dashboard

router = APIRouter(prefix="/api", tags=["生产看板"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    return build_dashboard(db)
