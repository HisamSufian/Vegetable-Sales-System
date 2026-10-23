"""SQLAlchemy models. They MAP onto the tables already created by schema.sql;
they do not create tables. Business rules (CHECK constraints) live in the
database, so bad data is rejected even if app code has a bug."""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, Computed, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

Money = Numeric(12, 2)


# ---------- Enums (names must match the Postgres enum types) ----------
class BuyerType(str, enum.Enum):
    LOCAL_SELLER = "LOCAL_SELLER"
    CONSUMER = "CONSUMER"

class ConsignmentStatus(str, enum.Enum):
    ARRIVED = "ARRIVED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"

class SalePaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CREDIT = "CREDIT"

class LedgerEntryType(str, enum.Enum):
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"

class PaymentMode(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    PDC = "PDC"

class PdcStatus(str, enum.Enum):
    PENDING = "PENDING"
    CLEARED = "CLEARED"
    BOUNCED = "BOUNCED"

class SettlementStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    FINAL = "FINAL"

class ExpenseType(str, enum.Enum):
    FARM_DEDUCTIBLE = "FARM_DEDUCTIBLE"
    INTERNAL = "INTERNAL"

class ExpenseCategory(str, enum.Enum):
    DRIVER_ADVANCE = "DRIVER_ADVANCE"
    PACKAGING_CARTONS = "PACKAGING_CARTONS"
    EXTRA_DAY_FEE = "EXTRA_DAY_FEE"
    CUSTOM_FARM_DEDUCTION = "CUSTOM_FARM_DEDUCTION"
    PARKING = "PARKING"
    UNLOADING_LABOR = "UNLOADING_LABOR"
    DELIVERY_LABOR = "DELIVERY_LABOR"
    CUSTOM_INTERNAL = "CUSTOM_INTERNAL"


def pg_enum(py_enum, name: str):
    # create_type=False -> the type already exists in the database
    return Enum(py_enum, name=name, create_type=False)

created_at_col = lambda: mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Master tables ----------
class FarmOwner(Base):
    __tablename__ = "farm_owners"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    default_margin_per_carton: Mapped[Decimal | None] = mapped_column(Money)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()


class DriverTruck(Base):
    __tablename__ = "drivers_trucks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plate_number: Mapped[str] = mapped_column(Text, unique=True)
    driver_name: Mapped[str] = mapped_column(Text)
    driver_phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class Vegetable(Base):
    __tablename__ = "vegetables"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    category: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class CompanyVehicle(Base):
    __tablename__ = "company_vehicles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plate_number: Mapped[str] = mapped_column(Text, unique=True)
    label: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Buyer(Base):
    __tablename__ = "buyers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    buyer_type: Mapped[BuyerType] = mapped_column(pg_enum(BuyerType, "buyer_type"), default=BuyerType.LOCAL_SELLER)
    credit_limit: Mapped[Decimal] = mapped_column(Money, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()


# ---------- Consignments ----------
class Consignment(Base):
    __tablename__ = "consignments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    farm_owner_id: Mapped[int] = mapped_column(ForeignKey("farm_owners.id"))
    driver_truck_id: Mapped[int] = mapped_column(ForeignKey("drivers_trucks.id"))
    arrival_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[ConsignmentStatus] = mapped_column(
        pg_enum(ConsignmentStatus, "consignment_status"), default=ConsignmentStatus.ARRIVED)
    verified_by: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    farm_owner: Mapped[FarmOwner] = relationship()
    driver_truck: Mapped[DriverTruck] = relationship()
    items: Mapped[list["ConsignmentItem"]] = relationship(back_populates="consignment", cascade="all, delete-orphan")


class ConsignmentItem(Base):
    __tablename__ = "consignment_items"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    consignment_id: Mapped[int] = mapped_column(ForeignKey("consignments.id", ondelete="CASCADE"))
    vegetable_id: Mapped[int] = mapped_column(ForeignKey("vegetables.id"))
    dispatched_cartons: Mapped[int] = mapped_column(Integer)
    unloaded_cartons: Mapped[int | None] = mapped_column(Integer)
    # calculated by the database; never written by us
    variance_cartons: Mapped[int | None] = mapped_column(
        Integer, Computed("unloaded_cartons - dispatched_cartons", persisted=True))

    consignment: Mapped[Consignment] = relationship(back_populates="items")
    vegetable: Mapped[Vegetable] = relationship()


# ---------- Stock & transfers ----------
class ItemStock(Base):
    __tablename__ = "item_stock"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    consignment_item_id: Mapped[int] = mapped_column(ForeignKey("consignment_items.id"))
    company_vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("company_vehicles.id"))  # None = original truck
    cartons_on_hand: Mapped[int] = mapped_column(Integer, default=0)

    consignment_item: Mapped[ConsignmentItem] = relationship()
    company_vehicle: Mapped[CompanyVehicle | None] = relationship()


class InventoryTransfer(Base):
    __tablename__ = "inventory_transfers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    consignment_item_id: Mapped[int] = mapped_column(ForeignKey("consignment_items.id"))
    from_company_vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("company_vehicles.id"))
    to_company_vehicle_id: Mapped[int] = mapped_column(ForeignKey("company_vehicles.id"))
    cartons: Mapped[int] = mapped_column(Integer)
    transferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)


# ---------- Sales ----------
class SalesTransaction(Base):
    __tablename__ = "sales_transactions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("buyers.id"))
    sale_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payment_method: Mapped[SalePaymentMethod] = mapped_column(pg_enum(SalePaymentMethod, "sale_payment_method"))
    total_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    buyer: Mapped[Buyer | None] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales_transactions.id", ondelete="CASCADE"))
    consignment_item_id: Mapped[int] = mapped_column(ForeignKey("consignment_items.id"))
    item_stock_id: Mapped[int] = mapped_column(ForeignKey("item_stock.id"))
    cartons: Mapped[int] = mapped_column(Integer)
    price_per_carton: Mapped[Decimal] = mapped_column(Money)
    farm_rate_per_carton: Mapped[Decimal] = mapped_column(Money)   # what the FARM gets per carton
    # calculated by the database; never written by us
    line_total: Mapped[Decimal | None] = mapped_column(Money, Computed("cartons * price_per_carton", persisted=True))
    margin_per_carton: Mapped[Decimal | None] = mapped_column(Money, Computed("price_per_carton - farm_rate_per_carton", persisted=True))
    farm_payout: Mapped[Decimal | None] = mapped_column(Money, Computed("cartons * farm_rate_per_carton", persisted=True))

    sale: Mapped[SalesTransaction] = relationship(back_populates="items")
    consignment_item: Mapped[ConsignmentItem] = relationship()


# ---------- Buyer ledger ----------
class BuyerLedger(Base):
    __tablename__ = "buyer_ledger"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    entry_date: Mapped[date] = mapped_column(Date, default=date.today)
    entry_type: Mapped[LedgerEntryType] = mapped_column(pg_enum(LedgerEntryType, "ledger_entry_type"))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales_transactions.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    payment_mode: Mapped[PaymentMode | None] = mapped_column(pg_enum(PaymentMode, "payment_mode"))
    cheque_number: Mapped[str | None] = mapped_column(Text)
    cheque_date: Mapped[date | None] = mapped_column(Date)
    pdc_status: Mapped[PdcStatus | None] = mapped_column(pg_enum(PdcStatus, "pdc_status"))
    reference_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class BuyerPaymentAllocation(Base):
    __tablename__ = "buyer_payment_allocations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payment_ledger_id: Mapped[int] = mapped_column(ForeignKey("buyer_ledger.id", ondelete="CASCADE"))
    invoice_ledger_id: Mapped[int] = mapped_column(ForeignKey("buyer_ledger.id"))
    amount: Mapped[Decimal] = mapped_column(Money)


# ---------- Farm settlements, payments, expenses ----------
class FarmOwnerSettlement(Base):
    __tablename__ = "farm_owner_settlements"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    farm_owner_id: Mapped[int] = mapped_column(ForeignKey("farm_owners.id"))
    settlement_date: Mapped[date] = mapped_column(Date)
    cartons_sold: Mapped[int] = mapped_column(Integer, default=0)
    gross_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    total_deductions: Mapped[Decimal] = mapped_column(Money, default=0)
    net_payout: Mapped[Decimal] = mapped_column(Money, default=0)
    status: Mapped[SettlementStatus] = mapped_column(
        pg_enum(SettlementStatus, "settlement_status"), default=SettlementStatus.DRAFT)
    created_at: Mapped[datetime] = created_at_col()


class FarmOwnerPayment(Base):
    __tablename__ = "farm_owner_payments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    farm_owner_id: Mapped[int] = mapped_column(ForeignKey("farm_owners.id"))
    payment_date: Mapped[date] = mapped_column(Date, default=date.today)
    amount: Mapped[Decimal] = mapped_column(Money)
    mode: Mapped[PaymentMode] = mapped_column(pg_enum(PaymentMode, "payment_mode"), default=PaymentMode.CASH)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class OperationalExpense(Base):
    __tablename__ = "operational_expenses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expense_type: Mapped[ExpenseType] = mapped_column(pg_enum(ExpenseType, "expense_type"))
    category: Mapped[ExpenseCategory] = mapped_column(pg_enum(ExpenseCategory, "expense_category"))
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Money)
    expense_date: Mapped[date] = mapped_column(Date, default=date.today)
    farm_owner_id: Mapped[int | None] = mapped_column(ForeignKey("farm_owners.id"))
    consignment_id: Mapped[int | None] = mapped_column(ForeignKey("consignments.id"))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales_transactions.id"))
    is_daily_overhead: Mapped[bool] = mapped_column(Boolean, default=False)
    settlement_id: Mapped[int | None] = mapped_column(ForeignKey("farm_owner_settlements.id"))
    created_at: Mapped[datetime] = created_at_col()
