# tests/unit/test_risk.py
import pytest
import pandas as pd
from core.models import RiskAssessment
from core.constants import PositionLevel
from services.risk_service import RiskService

def test_calculate_atr_with_insufficient_data():
    """邊界條件：資料筆數不夠計算 ATR"""
    df = pd.DataFrame({'High': [100], 'Low': [90], 'Close': [95]})
    atr = RiskService.calculate_atr(df, period=14)
    assert atr is None

def test_get_volatility_flag():
    """邏輯測試：波動率標籤判定"""
    # 正常波動 (ATR/Close <= 0.03)
    assert RiskService.get_volatility_flag(2.0, 100.0) == "Normal"
    # 高度波動 (0.03 < ratio <= 0.05)
    assert RiskService.get_volatility_flag(4.0, 100.0) == "High"
    # 極端波動 (ratio > 0.05)
    assert RiskService.get_volatility_flag(6.0, 100.0) == "Extreme"

def test_evaluate_risk_extreme_volatility_downgrades_position():
    """邏輯測試：極端波動時必須強制降倉"""
    # 建立可以算出大波動的假資料
    data = []
    for _ in range(20):
        # 每天波動 10 元 (10% on price 100)
        data.append({'High': 110, 'Low': 100, 'Close': 105})
    df = pd.DataFrame(data)
    
    risk_assess = RiskService.evaluate_risk(df, current_price=105.0, initial_position=PositionLevel.FULL)
    
    assert risk_assess.volatility_flag == "Extreme"
    # 從 FULL 降倉一次變成 HEAVY 或 MEDIUM (甚至因為單筆風險過大再降)
    # 起碼不會維持 FULL
    assert risk_assess.position_level != PositionLevel.FULL
