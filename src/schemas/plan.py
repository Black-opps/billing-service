# billing-service/src/schemas/plan.py
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


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
    billing_interval: BillingInterval = (
        BillingInterval.MONTHLY
    )  # Changed from 'interval' to match API
    features: List[str] = []
    limits: Dict = {}
    is_active: bool = True
    is_public: bool = True
    badge: Optional[str] = None
    display_order: int = 0


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
    display_order: Optional[int] = None


class PlanResponse(PlanBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Changed from 'orm_mode' for Pydantic v2
