"""Pydantic schemas: define what data the API accepts and returns.
(Separate from models.py, which describes database tables.)"""
from pydantic import BaseModel, ConfigDict, Field


class VegetableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str | None = None


class VegetableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # allow reading from DB objects
    id: int
    name: str
    category: str | None
