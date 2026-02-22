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
    signal: str  # e.g., "BUY", "SELL", "WAIT"
    mode: str    # e.g., "Trend Following", "Stock Picking"
    market_regime: str
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    target_price: Optional[float] = None
    exit_conditions: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    valuation_warning: bool = False
    
class TradeLogRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    code: str
    buy_price: float
    current_price: float
    qty: int
    fee_discount: float = 1.0

class TradeLogResponse(BaseModel):
    code: str
    buy_price: float
    current_price: float
    qty: int
    cost_basis: int
    market_value: int
    raw_profit: int
    buy_fee: int
    sell_fee: int
    tax: int
    total_cost: int
    net_profit: int
    roi_pct: float
    status: str # "Win" or "Loss"

class FundFlowDetail(BaseModel):
    code: str
    name: str
    net_buy_sell: int

class SectorFlowReport(BaseModel):
    sector_name: str
    total_net_flow: int
    details: List[FundFlowDetail] = Field(default_factory=list)
