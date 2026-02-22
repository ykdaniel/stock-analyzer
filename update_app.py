import re
import sys

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add imports at the top
imports = """
from core.constants import SectorType, PositionLevel, POSITION_ORDER, PE_EXPENSIVE_THRESHOLD, PE_REASONABLE_BASE, PE_GROWTH_MULTIPLIER, SECTOR_LIST, STOCK_DB
from core.models import ValuationRequest, RiskAssessment, StrategySignal
from repository.market_data_repo import MarketDataRepository
from services.valuation_service import ValuationService
from services.risk_service import RiskService
from services.strategy_engine import StrategyEngine
"""

# simple string replacement approach for safety
content = content.replace("import streamlit as st", imports + "\nimport streamlit as st")

# Remove ATR_CACHE
content = re.sub(r'ATR_CACHE:.*\n', '', content)

# Remove old function definitions by slicing out their blocks. Since this is complex, we will stub them out 
# to directly call the new services, which preserves the rest of the UI code that calls them.

# 1. get_stock_display_name
content = re.sub(
    r'def get_stock_display_name\(code: str\):(.*?)(?=\n#|\ndef )',
    r'def get_stock_display_name(code: str):\n    return MarketDataRepository.get_stock_display_name(code)\n',
    content,
    flags=re.DOTALL
)

# 2. normalize_stock_id
content = re.sub(
    r'def normalize_stock_id\(code: str\):(.*?)(?=\n#|\ndef )',
    r'def normalize_stock_id(code: str):\n    return MarketDataRepository.normalize_stock_id(code)\n',
    content,
    flags=re.DOTALL
)

# 3. get_reasonable_pe
content = re.sub(
    r'def get_reasonable_pe\(yoy_growth: Optional\[float\]\):(.*?)(?=\n#|\ndef )',
    r'def get_reasonable_pe(yoy_growth: Optional[float]):\n    return ValuationService.get_reasonable_pe(yoy_growth)\n',
    content,
    flags=re.DOTALL
)

# 4. get_valuation_status
content = re.sub(
    r'def get_valuation_status\(pe: Optional\[float\], eps: Optional\[float\], yoy_growth: Optional\[float\]\) -> Dict\[str, Any\]:(.*?)(?=\n#|\ndef )',
    r'def get_valuation_status(pe: Optional[float], eps: Optional[float], yoy_growth: Optional[float]) -> dict:\n    resp = ValuationService.get_valuation_status(ValuationRequest(pe=pe, eps=eps, yoy_growth=yoy_growth))\n    return {"status": resp.status, "warning": resp.warning, "reason": resp.reason, "reasonable_pe": resp.reasonable_pe}\n',
    content,
    flags=re.DOTALL
)

# 5. calculate_atr
content = re.sub(
    r'def calculate_atr\(df: pd\.DataFrame, period: int = 14\):(.*?)(?=\n#|\ndef )',
    r'def calculate_atr(df: pd.DataFrame, period: int = 14):\n    return RiskService.calculate_atr(df, period)\n',
    content,
    flags=re.DOTALL
)

# 6. get_volatility_flag
content = re.sub(
    r'def get_volatility_flag\(atr: float, close: float\):(.*?)(?=\n#|\ndef )',
    r'def get_volatility_flag(atr: float, close: float):\n    return RiskService.get_volatility_flag(atr, close)\n',
    content,
    flags=re.DOTALL
)

# 7. adjust_position_down
content = re.sub(
    r'def adjust_position_down\(current_level: str\):(.*?)(?=\n#|\ndef )',
    r'def adjust_position_down(current_level: str):\n    return RiskService.adjust_position_down(PositionLevel(current_level)).value\n',
    content,
    flags=re.DOTALL
)

# 8. calculate_tradelog
content = re.sub(
    r'def calculate_tradelog\(code, buy_price, current_price, qty, fee_discount=1\.0\):(.*?)(?=\n#|\ndef )',
    r'def calculate_tradelog(code, buy_price, current_price, qty, fee_discount=1.0):\n    return StrategyEngine.calculate_tradelog(code, buy_price, current_price, qty, fee_discount)\n',
    content,
    flags=re.DOTALL
)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced logic with service calls successfully.")
