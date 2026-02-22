from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SignalSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class TelemetryEvent(BaseModel):
    timestamp: datetime
    component: str
    event_type: str
    severity: SignalSeverity
    details: Dict[str, Any] = {}
    
class TierUsageEvent(TelemetryEvent):
    selector_name: str
    attempted_tier: int
    success_tier: int
    duration_ms: float
