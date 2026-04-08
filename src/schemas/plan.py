from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from enum import Enum


class BillingInterval(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    QUARTERLY = "quarterly"


class PlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    plan_id: str
    price: float
    currency: str = "KES"
    interval: BillingInterval = BillingInterval.MONTHLY
    features: List[str] = []
    limits: Dict = {}
    is_active: bool = True
    is_public: bool = True
    badge: Optional[str] = None


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    features: Optional[List[str]] = None
    limits: Optional[Dict] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    badge: Optional[str] = None


class PlanResponse(PlanBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PriceCalculationRequest(BaseModel):
    plan_id: str
    quantity: int = 1
    coupon_code: Optional[str] = None
    interval: str = "monthly"


class PriceCalculationResponse(BaseModel):
    plan: Dict
    quantity: int
    base_price: float
    discount: float
    subtotal: float
    tax: float
    tax_rate: float
    total: float
    currency: str
    interval: str