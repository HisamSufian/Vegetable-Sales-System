from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Buyer, CompanyVehicle, DriverTruck, FarmOwner
from app.utils import get_or_404

router = APIRouter(tags=["Master data"])


def apply_updates(obj, data):
    """Copy only the fields the caller actually sent onto the DB object."""
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)


# ======================= FARM OWNERS =======================
@router.get("/farm-owners/", response_model=list[schemas.FarmOwnerOut])
def list_farm_owners(active_only: bool = True, db: Session = Depends(get_db)):
    q = select(FarmOwner).order_by(FarmOwner.name)
    if active_only:
        q = q.where(FarmOwner.is_active.is_(True))
    return db.scalars(q).all()


@router.post("/farm-owners/", response_model=schemas.FarmOwnerOut, status_code=201)
def create_farm_owner(data: schemas.FarmOwnerCreate, db: Session = Depends(get_db)):
    owner = FarmOwner(name=data.name.strip(), contact_phone=data.contact_phone,
                      default_margin_per_carton=data.default_margin_per_carton)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


@router.patch("/farm-owners/{owner_id}", response_model=schemas.FarmOwnerOut)
def update_farm_owner(owner_id: int, data: schemas.FarmOwnerUpdate, db: Session = Depends(get_db)):
    owner = get_or_404(db, FarmOwner, owner_id, "Farm owner")
    apply_updates(owner, data)
    db.commit()
    db.refresh(owner)
    return owner


@router.get("/farm-owners/{owner_id}/balance")
def farm_owner_balance(owner_id: int, db: Session = Depends(get_db)):
    """Running balance we owe this farm owner (from the database view)."""
    owner = get_or_404(db, FarmOwner, owner_id, "Farm owner")
    balance = db.execute(
        text("SELECT balance_payable FROM v_farm_owner_balance WHERE farm_owner_id = :i"),
        {"i": owner_id},
    ).scalar()
    return {"farm_owner_id": owner.id, "name": owner.name, "balance_payable": balance}


# ======================= DRIVERS / TRUCKS =======================
@router.get("/trucks/", response_model=list[schemas.TruckOut])
def list_trucks(db: Session = Depends(get_db)):
    return db.scalars(select(DriverTruck).order_by(DriverTruck.plate_number)).all()


@router.post("/trucks/", response_model=schemas.TruckOut, status_code=201)
def create_truck(data: schemas.TruckCreate, db: Session = Depends(get_db)):
    plate = data.plate_number.strip().upper()
    if db.scalar(select(DriverTruck).where(DriverTruck.plate_number == plate)):
        raise HTTPException(status_code=409, detail="A truck with this plate already exists")
    truck = DriverTruck(plate_number=plate, driver_name=data.driver_name.strip(),
                        driver_phone=data.driver_phone)
    db.add(truck)
    db.commit()
    db.refresh(truck)
    return truck


@router.patch("/trucks/{truck_id}", response_model=schemas.TruckOut)
def update_truck(truck_id: int, data: schemas.TruckUpdate, db: Session = Depends(get_db)):
    """Change the driver name/phone (the same plate often has a different driver)."""
    truck = get_or_404(db, DriverTruck, truck_id, "Truck")
    apply_updates(truck, data)
    db.commit()
    db.refresh(truck)
    return truck


# ======================= COMPANY VEHICLES =======================
@router.get("/company-vehicles/", response_model=list[schemas.CompanyVehicleOut])
def list_company_vehicles(db: Session = Depends(get_db)):
    return db.scalars(select(CompanyVehicle).order_by(CompanyVehicle.plate_number)).all()


@router.post("/company-vehicles/", response_model=schemas.CompanyVehicleOut, status_code=201)
def create_company_vehicle(data: schemas.CompanyVehicleCreate, db: Session = Depends(get_db)):
    plate = data.plate_number.strip().upper()
    if db.scalar(select(CompanyVehicle).where(CompanyVehicle.plate_number == plate)):
        raise HTTPException(status_code=409, detail="A company vehicle with this plate already exists")
    vehicle = CompanyVehicle(plate_number=plate, label=data.label)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.patch("/company-vehicles/{vehicle_id}", response_model=schemas.CompanyVehicleOut)
def update_company_vehicle(vehicle_id: int, data: schemas.CompanyVehicleUpdate,
                           db: Session = Depends(get_db)):
    vehicle = get_or_404(db, CompanyVehicle, vehicle_id, "Company vehicle")
    apply_updates(vehicle, data)
    db.commit()
    db.refresh(vehicle)
    return vehicle


# ======================= BUYERS =======================
@router.get("/buyers/", response_model=list[schemas.BuyerOut])
def list_buyers(active_only: bool = True, db: Session = Depends(get_db)):
    q = select(Buyer).order_by(Buyer.name)
    if active_only:
        q = q.where(Buyer.is_active.is_(True))
    return db.scalars(q).all()


@router.post("/buyers/", response_model=schemas.BuyerOut, status_code=201)
def create_buyer(data: schemas.BuyerCreate, db: Session = Depends(get_db)):
    buyer = Buyer(name=data.name.strip(), phone=data.phone,
                  buyer_type=data.buyer_type, credit_limit=data.credit_limit)
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


@router.patch("/buyers/{buyer_id}", response_model=schemas.BuyerOut)
def update_buyer(buyer_id: int, data: schemas.BuyerUpdate, db: Session = Depends(get_db)):
    buyer = get_or_404(db, Buyer, buyer_id, "Buyer")
    apply_updates(buyer, data)
    db.commit()
    db.refresh(buyer)
    return buyer


@router.get("/buyers/{buyer_id}/balance")
def buyer_balance(buyer_id: int, db: Session = Depends(get_db)):
    """Outstanding amount this buyer owes us (from the database view)."""
    buyer = get_or_404(db, Buyer, buyer_id, "Buyer")
    balance = db.execute(
        text("SELECT balance_receivable FROM v_buyer_balance WHERE buyer_id = :i"),
        {"i": buyer_id},
    ).scalar()
    return {"buyer_id": buyer.id, "name": buyer.name, "balance_receivable": balance}
