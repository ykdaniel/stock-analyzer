# repository/fund_flow_repo.py
import pandas as pd
from typing import Optional, List
import datetime
import logging

logger = logging.getLogger(__name__)

class FundFlowRepository:
    """
    資金流向資料訪問層：
    負責透過 FinMind 取得三大法人淨買賣超數據。
    處理 API 連線異常與空資料防呆。
    """
    
    @staticmethod
    def get_institutional_buy_sell(date_str: str) -> Optional[pd.DataFrame]:
        """
        取得指定日期的三大法人買賣超明細
        回傳 DataFrame 包含: stock_id, buy, sell, name
        若無資料回傳 None
        """
        try:
            # Check if FinMind is accessible
            from FinMind.data import DataLoader
            dl = DataLoader()
            
            # API: TaiwanStockInstitutionalInvestorsBuySell
            df = dl.taiwan_stock_institutional_investors_buy_sell(
                stock_id="", # Empty means all stocks
                start_date=date_str,
                end_date=date_str
            )
            
            if df is None or df.empty:
                return None
                
            return df
            
        except ImportError:
            logger.error("FinMind is not installed.")
            return None
        except Exception as e:
            logger.error(f"Error fetching institutional data: {e}")
            return None
            
    @staticmethod
    def get_latest_trading_date() -> str:
        """
        推算最近的一個交易日 (簡單邏輯：略過週末，若今日已收盤且有資料則用今日，否則往前推)
        實務上，可以直接嘗試昨天，或往前找直到有資料的日期。
        這裡我們預設回傳「昨天」或「上週五」。
        """
        today = datetime.datetime.now()
        
        # 若在今天下午 3 點前，可能還沒有今天的盤後資料，保守起見用昨天
        if today.hour < 15:
            target_date = today - datetime.timedelta(days=1)
        else:
            target_date = today
            
        # 若是週末，退回到週五
        if target_date.weekday() == 5: # Saturday
            target_date = target_date - datetime.timedelta(days=1)
        elif target_date.weekday() == 6: # Sunday
            target_date = target_date - datetime.timedelta(days=2)
            
        return target_date.strftime("%Y-%m-%d")
