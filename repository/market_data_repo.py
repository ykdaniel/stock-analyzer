# repository/market_data_repo.py
import yfinance as yf
import pandas as pd
from typing import Optional
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


