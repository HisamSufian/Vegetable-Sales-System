from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import (
    Consignment, ExpenseCategory, ExpenseType, FarmOwner, OperationalExpense, SalesTransaction,
)
from app.utils import get_or_404

router = APIRouter(prefix="/expenses", tags=["Expenses"])

FARM_CATEGORIES = {
    ExpenseCategory.DRIVER_ADVANCE, ExpenseCategory.PACKAGING_CARTONS,
    ExpenseCategory.EXTRA_DAY_FEE, ExpenseCategory.CUSTOM_FARM_DEDUCTION,
}
INTERNAL_CATEGORIES = {
    ExpenseCategory.PARKING, ExpenseCategory.UNLOADING_LABOR,
    ExpenseCategory.DELIVERY_LABOR, ExpenseCategory.CUSTOM_INTERNAL,
}
CUSTOM_CATEGORIES = {ExpenseCategory.CUSTOM_FARM_DEDUCTION, ExpenseCategory.CUSTOM_INTERNAL}


def bad(msg: str):
    raise HTTPException(status_code=422, detail=msg)


@router.post("/manual", response_model=schemas.ExpenseOut, status_code=201)
def add_manual_expense(data: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    """Add any manual fee.
    FARM_DEDUCTIBLE -> reduces the farm owner's payout (needs farm_owner_id or consignment_id).
    INTERNAL        -> our own cost (needs consignment_id, sale_id, or is_daily_overhead=true)."""
    is_farm = data.expense_type == ExpenseType.FARM_DEDUCTIBLE
    allowed = FARM_CATEGORIES if is_farm else INTERNAL_CATEGORIES
    if data.category not in allowed:
        bad(f"Category {data.category.value} is not valid for {data.expense_type.value}. "
            f"Allowed: {sorted(c.value for c in allowed)}")
    if data.category in CUSTOM_CATEGORIES and not (data.description and data.description.strip()):
        bad("A description is required for custom expenses")

    consignment = get_or_404(db, Consignment, data.consignment_id, "Consignment") if data.consignment_id else None
    if data.sale_id:
        get_or_404(db, SalesTransaction, data.sale_id, "Sale")

    farm_owner_id = data.farm_owner_id
    if is_farm:
        if data.sale_id or data.is_daily_overhead:
            bad("Farm-deductible expenses link to a farm owner or consignment, not a sale or daily overhead")
        if consignment:
            if farm_owner_id and farm_owner_id != consignment.farm_owner_id:
                bad("farm_owner_id does not match the owner of that consignment")
            farm_owner_id = consignment.farm_owner_id
        if not farm_owner_id:
            bad("Provide farm_owner_id or consignment_id")
    else:
        if not (consignment or data.sale_id or data.is_daily_overhead):
            bad("Internal expenses must be tagged: give consignment_id, sale_id, or set is_daily_overhead=true")
    if farm_owner_id:
        get_or_404(db, FarmOwner, farm_owner_id, "Farm owner")

    exp = OperationalExpense(
        expense_type=data.expense_type, category=data.category,
        description=data.description.strip() if data.description else None,
        amount=data.amount, expense_date=data.expense_date or date.today(),
        farm_owner_id=farm_owner_id, consignment_id=data.consignment_id,
        sale_id=data.sale_id, is_daily_overhead=data.is_daily_overhead,
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.get("/", response_model=list[schemas.ExpenseOut])
def list_expenses(expense_type: ExpenseType | None = None, farm_owner_id: int | None = None,
                  consignment_id: int | None = None, date_from: date | None = None,
                  date_to: date | None = None, pending_only: bool = False,
                  db: Session = Depends(get_db)):
    """pending_only=true -> only farm deductions not yet applied to a settlement."""
    q = select(OperationalExpense).order_by(OperationalExpense.expense_date.desc(),
                                            OperationalExpense.id.desc())
    if expense_type:
        q = q.where(OperationalExpense.expense_type == expense_type)
    if farm_owner_id:
        q = q.where(OperationalExpense.farm_owner_id == farm_owner_id)
    if consignment_id:
        q = q.where(OperationalExpense.consignment_id == consignment_id)
    if date_from:
        q = q.where(OperationalExpense.expense_date >= date_from)
    if date_to:
        q = q.where(OperationalExpense.expense_date <= date_to)
    if pending_only:
        q = q.where(OperationalExpense.settlement_id.is_(None))
    return db.scalars(q).all()


@router.get("/summary", response_model=list[schemas.ExpenseSummaryRow])
def expense_summary(date_from: date | None = None, date_to: date | None = None,
                    db: Session = Depends(get_db)):
    """Totals per type and category (feeds the dashboard)."""
    q = select(OperationalExpense.expense_type, OperationalExpense.category,
               func.sum(OperationalExpense.amount), func.count()
               ).group_by(OperationalExpense.expense_type, OperationalExpense.category)
    if date_from:
        q = q.where(OperationalExpense.expense_date >= date_from)
    if date_to:
        q = q.where(OperationalExpense.expense_date <= date_to)
    return [schemas.ExpenseSummaryRow(expense_type=t, category=c, total=tot, count=n)
            for t, c, tot, n in db.execute(q).all()]


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    """Remove a mistaken entry. Blocked once it has been deducted in a settlement."""
    exp = get_or_404(db, OperationalExpense, expense_id, "Expense")
    if exp.settlement_id is not None:
        raise HTTPException(status_code=400, detail="Already deducted in a farm settlement; cannot delete")
    db.delete(exp)
    db.commit()
