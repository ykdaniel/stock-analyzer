# tests/unit/test_valuation.py
import pytest
from core.models import ValuationRequest
from services.valuation_service import ValuationService

def test_missing_data_returns_unknown():
    """邊界條件：當 PE 或 EPS 缺失時，回傳資料不足"""
    req = ValuationRequest(pe=None, eps=None, yoy_growth=None)
    result = ValuationService.get_valuation_status(req)
    
    assert result.status == "unknown"
    assert "資料不足" in result.reason
    assert result.warning is False

def test_negative_pe_returns_unknown_with_warning():
    """邏輯防呆：PE 為負數表示虧損"""
    req = ValuationRequest(pe=-5.0, eps=-1.0, yoy_growth=-10.0)
    result = ValuationService.get_valuation_status(req)
    
    assert result.status == "unknown"
    assert result.warning is True
    assert "虧損" in result.reason

def test_expensive_valuation_triggers_warning():
    """邏輯測試：超過絕對高估線"""
    req = ValuationRequest(pe=45.0, eps=5.0, yoy_growth=10.0)
    result = ValuationService.get_valuation_status(req)
    
    assert result.status == "expensive"
    assert result.warning is True

def test_dynamic_valuation_with_high_growth():
    """邏輯測試：高本益比但同時也有高成長率"""
    # 預設超過 25 會被視為昂貴，但如果成長率大於 20，會獲得稍微寬容的 reasonable
    req = ValuationRequest(pe=28.0, eps=5.0, yoy_growth=35.0)
    result = ValuationService.get_valuation_status(req)
    
    assert result.status == "reasonable"
    assert result.warning is False
    assert result.reasonable_pe == 35.0  # 因為大於 30，動態 PE 擴張至 35
