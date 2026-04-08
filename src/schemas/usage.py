from pydantic import BaseModel
from typing import Optional, Dict, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class MetricType(str, Enum):
    COUNT = "count"
    DURATION = "duration"
    VOLUME = "volume"


class UsageRecordCreate(BaseModel):
    tenant_id: UUID
    metric_name: str
    quantity: int = 1
    service: str
    metadata: Optional[Dict] = {}
    idempotency_key: Optional[str] = None


class UsageRecordResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    metric_name: str
    quantity: int
    timestamp: datetime
    service: str

    class Config:
        orm_mode = True


class UsageSummaryResponse(BaseModel):
    tenant_id: UUID
    period: Dict
    usage: Dict
    limits: Dict


class UsageAlertResponse(BaseModel):
    metric: str
    threshold: float
    current_usage: int
    limit: int
    percentage: float