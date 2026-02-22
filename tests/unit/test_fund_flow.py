import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from core.models import FundFlowDetail, SectorFlowReport
from services.fund_flow_service import FundFlowService

@pytest.fixture
def mock_fund_flow_repo():
    with patch('services.fund_flow_service.FundFlowRepository') as mock_repo:
        mock_repo.get_latest_trading_date.return_value = "2023-10-27"
        
        # 模擬 FinMind 回傳的資料結構
        df = pd.DataFrame([
            {"stock_id": "2330", "buy": 1000, "sell": 200}, # 淨買 800 (半導體)
            {"stock_id": "2454", "buy": 300, "sell": 400},  # 淨賣 100 (半導體)
            {"stock_id": "2881", "buy": 500, "sell": 0},    # 淨買 500 (金融業)
            {"stock_id": "2882", "buy": 0, "sell": 600},    # 淨賣 600 (金融業)
        ])
        mock_repo.get_institutional_buy_sell.return_value = df
        yield mock_repo

@pytest.fixture
def mock_market_data_repo():
    with patch('services.fund_flow_service.MarketDataRepository') as mock_repo:
        def get_name(code):
            names = {"2330.TW": "台積電", "2454.TW": "聯發科", "2881.TW": "富邦金", "2882.TW": "國泰金"}
            return names.get(f"{code}.TW", str(code))
        mock_repo.get_stock_display_name.side_effect = get_name
        yield mock_repo

@pytest.fixture
def mock_sector_list():
    sectors = {
        "半導體": ["2330.TW", "2454.TW", "2303.TW"], # 2303 無交易紀錄
        "金融業": ["2881.TW", "2882.TW"],
        "航運業": ["2603.TW"] # 無交易紀錄
    }
    with patch('services.fund_flow_service.SECTOR_LIST', sectors):
        yield sectors

def test_get_sector_fund_flow_report_empty(mock_fund_flow_repo):
    """當沒有資料時，應該回傳 None"""
    mock_fund_flow_repo.get_institutional_buy_sell.return_value = pd.DataFrame()
    result = FundFlowService.get_sector_fund_flow_report()
    assert result is None

def test_get_sector_fund_flow_report_aggregation_and_sorting(mock_fund_flow_repo, mock_market_data_repo, mock_sector_list):
    """正確聚合各類股資金，依總金額降冪排序，並忽略無交易的類股"""
    reports = FundFlowService.get_sector_fund_flow_report()
    
    # 總共 2 個類股有紀錄 (半導體, 金融業)
    assert len(reports) == 2
    
    # 半導體: 800 - 100 = 700
    # 金融業: 500 - 600 = -100
    # 排序應該是 半導體 (700) -> 金融業 (-100)
    
    assert reports[0].sector_name == "半導體"
    assert reports[0].total_net_flow == 700
    
    # 檢查細項
    assert len(reports[0].details) == 2
    assert reports[0].details[0].code == "2330.TW"
    assert reports[0].details[0].net_buy_sell == 800
    assert reports[0].details[1].code == "2454.TW"
    assert reports[0].details[1].net_buy_sell == -100

    assert reports[1].sector_name == "金融業"
    assert reports[1].total_net_flow == -100

def test_get_latest_date_available(mock_fund_flow_repo):
    date = FundFlowService.get_latest_date_available()
    assert date == "2023-10-27"
    mock_fund_flow_repo.get_latest_trading_date.assert_called_once()

