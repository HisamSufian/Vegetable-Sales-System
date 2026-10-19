from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Vegetable
from app.schemas import VegetableCreate, VegetableOut

router = APIRouter(prefix="/vegetables", tags=["Vegetables"])


@router.get("/", response_model=list[VegetableOut])
def list_vegetables(db: Session = Depends(get_db)):
    return db.scalars(select(Vegetable).order_by(Vegetable.name)).all()


@router.post("/", response_model=VegetableOut, status_code=201)
def create_vegetable(data: VegetableCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(Vegetable).where(Vegetable.name == data.name))
    if exists:
        raise HTTPException(status_code=409, detail="Vegetable already exists")
    veg = Vegetable(name=data.name, category=data.category)
    db.add(veg)
    db.commit()
    db.refresh(veg)
    return veg
