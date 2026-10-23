from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import schemas
from app.database import get_db
from app.models import (
    CompanyVehicle, Consignment, ConsignmentItem, InventoryTransfer, ItemStock,
)
from app.utils import get_or_404

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _location(s: ItemStock) -> tuple[str, str]:
    """(type, readable name) of where a stock row physically is."""
    if s.company_vehicle_id is None:
        t = s.consignment_item.consignment.driver_truck
        return "DRIVER_TRUCK", f"Truck {t.plate_number} (driver {t.driver_name})"
    v = s.company_vehicle
    return "COMPANY_VEHICLE", f"Company vehicle {v.plate_number}" + (f" - {v.label}" if v.label else "")


def _stock_row(db: Session, item_id: int, vehicle_id: int | None, lock: bool = False):
    q = select(ItemStock).where(
        ItemStock.consignment_item_id == item_id,
        ItemStock.company_vehicle_id.is_(None) if vehicle_id is None
        else ItemStock.company_vehicle_id == vehicle_id,
    )
    return db.scalar(q.with_for_update() if lock else q)


@router.post("/transfer", response_model=schemas.TransferOut, status_code=201)
def transfer_stock(data: schemas.TransferIn, db: Session = Depends(get_db)):
    """Move unsold cartons of one batch from a driver's truck (or another company
    vehicle) into a company vehicle. The batch keeps its farm owner and batch id."""
    item = get_or_404(db, ConsignmentItem, data.consignment_item_id, "Batch item")
    dest = get_or_404(db, CompanyVehicle, data.to_company_vehicle_id, "Company vehicle")
    if not dest.is_active:
        raise HTTPException(status_code=400, detail="Destination vehicle is inactive")
    if data.from_company_vehicle_id is not None:
        get_or_404(db, CompanyVehicle, data.from_company_vehicle_id, "Source company vehicle")
    if data.from_company_vehicle_id == data.to_company_vehicle_id:
        raise HTTPException(status_code=400, detail="Source and destination are the same")

    src = _stock_row(db, item.id, data.from_company_vehicle_id, lock=True)
    available = src.cartons_on_hand if src else 0
    if data.cartons > available:
        raise HTTPException(status_code=400,
                            detail=f"Only {available} cartons available at the source location")

    dst = _stock_row(db, item.id, dest.id, lock=True)
    if dst is None:
        dst = ItemStock(consignment_item_id=item.id, company_vehicle_id=dest.id, cartons_on_hand=0)
        db.add(dst)

    src.cartons_on_hand -= data.cartons
    dst.cartons_on_hand += data.cartons
    transfer = InventoryTransfer(
        consignment_item_id=item.id, from_company_vehicle_id=data.from_company_vehicle_id,
        to_company_vehicle_id=dest.id, cartons=data.cartons, note=data.note)
    db.add(transfer)
    db.commit()

    c = item.consignment
    return schemas.TransferOut(
        transfer_id=transfer.id, consignment_id=c.id, consignment_item_id=item.id,
        farm_owner_id=c.farm_owner_id, farm_owner_name=c.farm_owner.name,
        vegetable_name=item.vegetable.name, cartons_moved=data.cartons,
        from_location=_location(src)[1], to_location=_location(dst)[1],
        remaining_at_source=src.cartons_on_hand, now_at_destination=dst.cartons_on_hand,
    )


@router.get("/stock", response_model=list[schemas.StockOut])
def list_stock(farm_owner_id: int | None = None, vegetable_id: int | None = None,
               company_vehicle_id: int | None = None, only_available: bool = True,
               db: Session = Depends(get_db)):
    """Everything currently on hand, by batch and location. The POS uses item_stock_id."""
    q = (
        select(ItemStock)
        .join(ConsignmentItem, ItemStock.consignment_item_id == ConsignmentItem.id)
        .join(Consignment, ConsignmentItem.consignment_id == Consignment.id)
        .options(
            joinedload(ItemStock.consignment_item).joinedload(ConsignmentItem.vegetable),
            joinedload(ItemStock.consignment_item).joinedload(ConsignmentItem.consignment)
            .joinedload(Consignment.farm_owner),
            joinedload(ItemStock.consignment_item).joinedload(ConsignmentItem.consignment)
            .joinedload(Consignment.driver_truck),
            joinedload(ItemStock.company_vehicle),
        )
        .order_by(Consignment.arrival_date, ItemStock.id)
    )
    if only_available:
        q = q.where(ItemStock.cartons_on_hand > 0)
    if farm_owner_id:
        q = q.where(Consignment.farm_owner_id == farm_owner_id)
    if vegetable_id:
        q = q.where(ConsignmentItem.vegetable_id == vegetable_id)
    if company_vehicle_id:
        q = q.where(ItemStock.company_vehicle_id == company_vehicle_id)

    out = []
    for s in db.scalars(q).all():
        ci = s.consignment_item
        c = ci.consignment
        loc_type, loc_name = _location(s)
        out.append(schemas.StockOut(
            item_stock_id=s.id, consignment_item_id=ci.id, consignment_id=c.id,
            farm_owner_id=c.farm_owner_id, farm_owner_name=c.farm_owner.name,
            vegetable_id=ci.vegetable_id, vegetable_name=ci.vegetable.name,
            arrival_date=c.arrival_date, location_type=loc_type,
            company_vehicle_id=s.company_vehicle_id, location_name=loc_name,
            cartons_on_hand=s.cartons_on_hand,
        ))
    return out


@router.get("/transfers", response_model=list[schemas.TransferHistoryOut])
def transfer_history(consignment_item_id: int | None = None, db: Session = Depends(get_db)):
    q = select(InventoryTransfer).order_by(InventoryTransfer.id.desc())
    if consignment_item_id:
        q = q.where(InventoryTransfer.consignment_item_id == consignment_item_id)
    return db.scalars(q).all()
