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
        ticker_tw = f"{clean_code}.TW"
        
        # 1. 查本地 STOCK_DB
        info = STOCK_DB.get(ticker_tw)
        if info:
            return info['name']
        
        # 2. 回退到 yfinance 查詢
        try:
            ticker = yf.Ticker(ticker_tw)
            name = ticker.info.get("shortName", clean_code)
            return name
        except Exception:
            return clean_code
            
    @staticmethod
    def normalize_stock_id(code: str) -> str:
        """標準化股票代號：支援中文名稱反查，或自動補上 .TW 後綴並轉大寫"""
        clean = code.strip()
        if not clean:
            return ""
            
        # 1. 嘗試名稱反查
        matched_ticker = None
        for ticker, info in STOCK_DB.items():
            name = info.get('name', '')
            if clean == name:
                return ticker  # 優先完全比對
            if clean in name and not clean.isascii(): 
                # 若包含中文且部分命中，先記下來（以第一個命中的為主）
                if not matched_ticker:
                    matched_ticker = ticker
                    
        if matched_ticker:
            return matched_ticker
            
        # 2. 原始代號處理邏輯
        clean = clean.upper()
        if not clean.endswith(".TW"):
            clean += ".TW"
        return clean


