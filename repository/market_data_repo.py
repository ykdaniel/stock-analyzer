# repository/market_data_repo.py
import yfinance as yf
import pandas as pd
from typing import Optional, Tuple
from core.models import ValuationRequest
from core.constants import STOCK_DB
import datetime

class MarketDataRepository:
    """
    資料訪問層：負責與外部 API（yfinance, FinMind 或 resilience_adapter）溝通
    處理所有的 DataFrame 與 None 的空值邊界狀況，並回傳標準化資料。
    """
    
    @staticmethod
    def get_stock_display_name(code: str) -> str:
        """取得股票顯示名稱（優先中文）"""
        clean_code = code.replace(".TW", "").replace(".tw", "")
        # 1. 查本地 STOCK_DB
        info = STOCK_DB.get(clean_code)
        if info:
            return f"{clean_code} {info['name']}"
        
        # 2. 回退到 yfinance 查詢
        try:
            ticker = yf.Ticker(f"{clean_code}.TW")
            name = ticker.info.get("shortName", clean_code)
            return f"{clean_code} {name}"
        except Exception:
            return code
            
    @staticmethod
    def normalize_stock_id(code: str) -> str:
        """標準化股票代號：自動補上 .TW 後綴並轉大寫"""
        clean = code.strip().upper()
        if not clean.endswith(".TW"):
            clean += ".TW"
        return clean

    @staticmethod
    def fetch_technical_data(symbol: str, period_days: int = 365) -> Optional[pd.DataFrame]:
        """
        獲取日線技術資料
        返回的 df 必須確保包含 Open, High, Low, Close, Volume 欄位
        """
        start_date = (datetime.date.today() - datetime.timedelta(days=period_days)).isoformat()
        try:
            df = TechProvider.fetch_data(symbol, start_date)
            if df is None or df.empty:
                return None
            return df
        except Exception:
            # 發生網路錯誤或 API 故障時防呆
            return None

    @staticmethod
    def fetch_valuation_data(symbol: str) -> ValuationRequest:
        """
        獲取基本面估值資料，統一回傳 Pydantic Model 確保型別正確
        缺漏資料預設為 None
        """
        try:
            fun_data = FundamentalProvider.fetch_data(symbol)
            if not fun_data:
                 return ValuationRequest(pe=None, eps=None, yoy_growth=None)
            
            # 從 FinMind 回傳的資料結構中抽取
            # 假設結構：{'pe': float, 'eps': float, 'revenue_yoy': float} 
            # 這裡簡化對應，實際依 FundamentalProvider 實作為準
            return ValuationRequest(
                pe=fun_data.get('pe'),
                eps=fun_data.get('eps'),
                yoy_growth=fun_data.get('revenue_yoy')
            )
        except Exception:
            return ValuationRequest(pe=None, eps=None, yoy_growth=None)
