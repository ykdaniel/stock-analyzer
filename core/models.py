# core/models.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date
from .constants import PositionLevel

class ValuationRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    pe: Optional[float] = None
    eps: Optional[float] = None
    yoy_growth: Optional[float] = None

class ValuationResponse(BaseModel):
    status: str
    warning: bool
    reason: str
    reasonable_pe: float

class RiskAssessment(BaseModel):
    atr: float
    volatility_flag: str
    stop_loss_price: float
    position_level: PositionLevel
    risk_pct: float

class StrategySignal(BaseModel):
    signal: str  # e.g., "Buy", "Exit", "NoTrade", "Watch"
    mode: str    # e.g., "Trend Following", "Stock Picking", "A", "B", "NoTrade"
    market_regime: str # e.g., "BULL", "BEAR", "NEUTRAL"
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    target_price: Optional[float] = None
    atr: Optional[float] = None
    stop_loss_method: Optional[str] = None
    risk_pct: Optional[float] = None
    position_level: PositionLevel = Field(default=PositionLevel.NO_POSITION)
    exit_conditions: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    not_buy_reasons: List[str] = Field(default_factory=list)
    valuation_warning: bool = False
    watch: bool = False
    buy: bool = False
    confidence: int = 0


class FundFlowDetail(BaseModel):
    code: str
    name: str
    net_buy_sell: int

class SectorFlowReport(BaseModel):
    sector_name: str
    total_net_flow: int
    details: List[FundFlowDetail] = Field(default_factory=list)
