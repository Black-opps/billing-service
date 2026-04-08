from pydantic import BaseModel
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime
from enum import Enum


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"
    TRIALING = "trialing"


class SubscriptionBase(BaseModel):
    tenant_id: UUID
    plan_id: str
    billing_cycle: str = "monthly"
    quantity: int = 1
    auto_renew: bool = True
    has_trial: bool = False


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    auto_renew: Optional[bool] = None
    quantity: Optional[int] = None


class SubscriptionUpgrade(BaseModel):
    new_plan_id: str
    effective_date: Optional[datetime] = None


class SubscriptionCancel(BaseModel):
    immediate: bool = False
    reason: Optional[str] = None


class SubscriptionResponse(SubscriptionBase):
    id: UUID
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime
    plan: Optional[Dict] = None

    class Config:
        orm_mode = True