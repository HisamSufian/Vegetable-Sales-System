from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app import schemas
from app.database import get_db
from app.models import (
    Consignment, ConsignmentItem, ConsignmentStatus, DriverTruck, ExpenseCategory,
    ExpenseType, FarmOwner, ItemStock, OperationalExpense, Vegetable,
)
from app.utils import get_or_404

router = APIRouter(prefix="/consignments", tags=["Consignments"])


def _base_query():
    """Loads a consignment together with its items, owner and truck in few queries."""
    return select(Consignment).options(
        selectinload(Consignment.items).joinedload(ConsignmentItem.vegetable),
        joinedload(Consignment.farm_owner),
        joinedload(Consignment.driver_truck),
    )


def to_out(c: Consignment) -> schemas.ConsignmentOut:
    items = [
        schemas.ConsignmentItemOut(
            id=i.id, vegetable_id=i.vegetable_id, vegetable_name=i.vegetable.name,
            dispatched_cartons=i.dispatched_cartons, unloaded_cartons=i.unloaded_cartons,
            variance_cartons=i.variance_cartons,
        )
        for i in c.items
    ]
    return schemas.ConsignmentOut(
        id=c.id, farm_owner_id=c.farm_owner_id, farm_owner_name=c.farm_owner.name,
        driver_truck_id=c.driver_truck_id, plate_number=c.driver_truck.plate_number,
        driver_name=c.driver_truck.driver_name, arrival_date=c.arrival_date,
        status=c.status, verified_by=c.verified_by, notes=c.notes, items=items,
        total_dispatched=sum(i.dispatched_cartons for i in c.items),
        total_unloaded=sum(i.unloaded_cartons or 0 for i in c.items),
    )


def _load(db: Session, consignment_id: int) -> Consignment:
    c = db.scalar(_base_query().where(Consignment.id == consignment_id))
    if c is None:
        raise HTTPException(status_code=404, detail=f"Consignment {consignment_id} not found")
    return c


# ------------------------------------------------------------------
@router.post("/", response_model=schemas.ConsignmentOut, status_code=201)
def register_arrival(data: schemas.ConsignmentCreate, db: Session = Depends(get_db)):
    """Register a truck arrival: farm dispatch counts, optional unloaded counts,
    driver advance and packaging cost. Everything is saved together or not at all."""
    owner = get_or_404(db, FarmOwner, data.farm_owner_id, "Farm owner")
    if not owner.is_active:
        raise HTTPException(status_code=400, detail="This farm owner is inactive")
    get_or_404(db, DriverTruck, data.driver_truck_id, "Truck")

    veg_ids = [i.vegetable_id for i in data.items]
    if len(set(veg_ids)) != len(veg_ids):
        raise HTTPException(status_code=422, detail="Each vegetable can appear only once per truck")
    found = set(db.scalars(select(Vegetable.id).where(Vegetable.id.in_(veg_ids))))
    missing = set(veg_ids) - found
    if missing:
        raise HTTPException(status_code=404, detail=f"Vegetable id(s) not found: {sorted(missing)}")

    c = Consignment(
        farm_owner_id=data.farm_owner_id, driver_truck_id=data.driver_truck_id,
        arrival_date=data.arrival_date or date.today(),
        verified_by=data.verified_by, notes=data.notes,
    )
    for it in data.items:
        c.items.append(ConsignmentItem(
            vegetable_id=it.vegetable_id,
            dispatched_cartons=it.dispatched_cartons,
            unloaded_cartons=it.unloaded_cartons,
        ))
    db.add(c)
    db.flush()  # assigns ids without committing yet

    # One stock row per batch, sitting on the original truck.
    # Sellable stock = the VERIFIED unloaded count (0 until verified).
    for ci in c.items:
        db.add(ItemStock(consignment_item_id=ci.id, company_vehicle_id=None,
                         cartons_on_hand=ci.unloaded_cartons or 0))
    if all(ci.unloaded_cartons is not None for ci in c.items):
        c.status = ConsignmentStatus.VERIFIED

    # Farm-deductible costs recorded at arrival
    if data.driver_advance:
        db.add(OperationalExpense(
            expense_type=ExpenseType.FARM_DEDUCTIBLE, category=ExpenseCategory.DRIVER_ADVANCE,
            description="Driver cash advance", amount=data.driver_advance,
            expense_date=c.arrival_date, farm_owner_id=c.farm_owner_id, consignment_id=c.id))
    if data.packaging_cost:
        db.add(OperationalExpense(
            expense_type=ExpenseType.FARM_DEDUCTIBLE, category=ExpenseCategory.PACKAGING_CARTONS,
            description="Packaging cartons supplied to farm", amount=data.packaging_cost,
            expense_date=c.arrival_date, farm_owner_id=c.farm_owner_id, consignment_id=c.id))

    db.commit()
    return to_out(_load(db, c.id))


@router.post("/{consignment_id}/verify", response_model=schemas.ConsignmentOut)
def verify_unloading(consignment_id: int, data: schemas.VerifyIn, db: Session = Depends(get_db)):
    """Enter (or correct) the unloaded carton counts counted at market entry.
    Sellable stock on the original truck is adjusted by the difference."""
    c = _load(db, consignment_id)
    if c.status == ConsignmentStatus.CLOSED:
        raise HTTPException(status_code=400, detail="This consignment is closed")
    items_by_id = {i.id: i for i in c.items}

    for v in data.items:
        ci = items_by_id.get(v.consignment_item_id)
        if ci is None:
            raise HTTPException(status_code=422, detail=(
                f"Item {v.consignment_item_id} does not belong to consignment {consignment_id}"))
        delta = v.unloaded_cartons - (ci.unloaded_cartons or 0)
        stock = db.scalar(
            select(ItemStock)
            .where(ItemStock.consignment_item_id == ci.id, ItemStock.company_vehicle_id.is_(None))
            .with_for_update()
        )
        if stock.cartons_on_hand + delta < 0:
            raise HTTPException(status_code=400, detail=(
                f"Cannot lower item {ci.id} to {v.unloaded_cartons}: cartons have already "
                f"been sold or transferred from this truck"))
        stock.cartons_on_hand += delta
        ci.unloaded_cartons = v.unloaded_cartons

    if data.verified_by:
        c.verified_by = data.verified_by
    if all(i.unloaded_cartons is not None for i in c.items):
        c.status = ConsignmentStatus.VERIFIED
    db.commit()
    return to_out(_load(db, consignment_id))


@router.get("/", response_model=list[schemas.ConsignmentOut])
def list_consignments(arrival_date: date | None = None, status: ConsignmentStatus | None = None,
                      farm_owner_id: int | None = None, db: Session = Depends(get_db)):
    q = _base_query().order_by(Consignment.arrival_date.desc(), Consignment.id.desc())
    if arrival_date:
        q = q.where(Consignment.arrival_date == arrival_date)
    if status:
        q = q.where(Consignment.status == status)
    if farm_owner_id:
        q = q.where(Consignment.farm_owner_id == farm_owner_id)
    return [to_out(c) for c in db.scalars(q).all()]


@router.get("/{consignment_id}", response_model=schemas.ConsignmentDetail)
def get_consignment(consignment_id: int, db: Session = Depends(get_db)):
    c = _load(db, consignment_id)
    expenses = db.scalars(
        select(OperationalExpense).where(OperationalExpense.consignment_id == consignment_id)
        .order_by(OperationalExpense.id)
    ).all()
    return schemas.ConsignmentDetail(
        **to_out(c).model_dump(),
        expenses=[schemas.ExpenseBrief.model_validate(e) for e in expenses],
    )
