"""Pydantic schemas: define what data the API accepts and returns.
(Separate from models.py, which describes database tables.)"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models import BuyerType, ConsignmentStatus, ExpenseCategory, ExpenseType

# Money rules: max 12 digits, 2 decimals
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
NonNegMoney = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class ORM(BaseModel):
    """Base for response models: allows reading straight from DB objects."""
    model_config = ConfigDict(from_attributes=True)


# ---------- Vegetables ----------
class VegetableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str | None = None

class VegetableOut(ORM):
    id: int
    name: str
    category: str | None


# ---------- Farm owners ----------
class FarmOwnerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_phone: str | None = None
    default_margin_per_carton: NonNegMoney | None = None   # e.g. 5.00

class FarmOwnerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    contact_phone: str | None = None
    default_margin_per_carton: NonNegMoney | None = None
    is_active: bool | None = None

class FarmOwnerOut(ORM):
    id: int
    name: str
    contact_phone: str | None
    default_margin_per_carton: Decimal | None
    is_active: bool


# ---------- Drivers & trucks ----------
class TruckCreate(BaseModel):
    plate_number: str = Field(min_length=1, max_length=30)
    driver_name: str = Field(min_length=1, max_length=100)
    driver_phone: str | None = None

class TruckUpdate(BaseModel):
    driver_name: str | None = Field(default=None, min_length=1, max_length=100)
    driver_phone: str | None = None

class TruckOut(ORM):
    id: int
    plate_number: str
    driver_name: str
    driver_phone: str | None


# ---------- Company vehicles ----------
class CompanyVehicleCreate(BaseModel):
    plate_number: str = Field(min_length=1, max_length=30)
    label: str | None = None

class CompanyVehicleUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None

class CompanyVehicleOut(ORM):
    id: int
    plate_number: str
    label: str | None
    is_active: bool


# ---------- Buyers ----------
class BuyerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    phone: str | None = None
    buyer_type: BuyerType = BuyerType.LOCAL_SELLER
    credit_limit: NonNegMoney = Decimal("0")

class BuyerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = None
    buyer_type: BuyerType | None = None
    credit_limit: NonNegMoney | None = None
    is_active: bool | None = None

class BuyerOut(ORM):
    id: int
    name: str
    phone: str | None
    buyer_type: BuyerType
    credit_limit: Decimal
    is_active: bool


# ---------- Consignments ----------
class ConsignmentItemIn(BaseModel):
    vegetable_id: int
    dispatched_cartons: int = Field(gt=0, description="Count the farm says it sent")
    unloaded_cartons: int | None = Field(
        default=None, ge=0, description="Count verified at market entry (can be added later)")

class ConsignmentCreate(BaseModel):
    farm_owner_id: int
    driver_truck_id: int
    arrival_date: date | None = None          # defaults to today
    verified_by: str | None = None
    notes: str | None = None
    items: list[ConsignmentItemIn] = Field(min_length=1)
    driver_advance: PositiveMoney | None = None   # cash paid to driver upfront
    packaging_cost: PositiveMoney | None = None   # cost of boxes supplied to the farm

class VerifyItem(BaseModel):
    consignment_item_id: int
    unloaded_cartons: int = Field(ge=0)

class VerifyIn(BaseModel):
    verified_by: str | None = None
    items: list[VerifyItem] = Field(min_length=1)

class ConsignmentItemOut(BaseModel):
    id: int
    vegetable_id: int
    vegetable_name: str
    dispatched_cartons: int
    unloaded_cartons: int | None
    variance_cartons: int | None      # unloaded minus dispatched (negative = short)

class ConsignmentOut(BaseModel):
    id: int
    farm_owner_id: int
    farm_owner_name: str
    driver_truck_id: int
    plate_number: str
    driver_name: str
    arrival_date: date
    status: ConsignmentStatus
    verified_by: str | None
    notes: str | None
    items: list[ConsignmentItemOut]
    total_dispatched: int
    total_unloaded: int

class ExpenseBrief(ORM):
    id: int
    category: ExpenseCategory
    amount: Decimal
    description: str | None
    settlement_id: int | None         # filled once deducted from a farm statement

class ConsignmentDetail(ConsignmentOut):
    expenses: list[ExpenseBrief]


# ---------- Expenses ----------
class ExpenseCreate(BaseModel):
    expense_type: ExpenseType
    category: ExpenseCategory
    amount: PositiveMoney
    description: str | None = None
    expense_date: date | None = None            # defaults to today
    farm_owner_id: int | None = None
    consignment_id: int | None = None
    sale_id: int | None = None
    is_daily_overhead: bool = False

class ExpenseOut(ORM):
    id: int
    expense_type: ExpenseType
    category: ExpenseCategory
    description: str | None
    amount: Decimal
    expense_date: date
    farm_owner_id: int | None
    consignment_id: int | None
    sale_id: int | None
    is_daily_overhead: bool
    settlement_id: int | None

class ExpenseSummaryRow(BaseModel):
    expense_type: ExpenseType
    category: ExpenseCategory
    total: Decimal
    count: int


# ---------- Inventory ----------
class TransferIn(BaseModel):
    consignment_item_id: int
    to_company_vehicle_id: int
    cartons: int = Field(gt=0)
    from_company_vehicle_id: int | None = Field(
        default=None, description="Leave empty to take from the original driver truck")
    note: str | None = None

class TransferOut(BaseModel):
    transfer_id: int
    consignment_id: int
    consignment_item_id: int
    farm_owner_id: int
    farm_owner_name: str
    vegetable_name: str
    cartons_moved: int
    from_location: str
    to_location: str
    remaining_at_source: int
    now_at_destination: int

class TransferHistoryOut(ORM):
    id: int
    consignment_item_id: int
    from_company_vehicle_id: int | None
    to_company_vehicle_id: int
    cartons: int
    transferred_at: datetime
    note: str | None

class StockOut(BaseModel):
    item_stock_id: int            # the POS will use this to pick the source
    consignment_item_id: int
    consignment_id: int
    farm_owner_id: int
    farm_owner_name: str
    vegetable_id: int
    vegetable_name: str
    arrival_date: date
    location_type: str            # DRIVER_TRUCK or COMPANY_VEHICLE
    company_vehicle_id: int | None
    location_name: str
    cartons_on_hand: int
