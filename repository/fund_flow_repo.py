# repository/fund_flow_repo.py
import pandas as pd
from typing import Optional, List
import datetime
import logging
import concurrent.futures
from core.constants import SECTOR_LIST

logger = logging.getLogger(__name__)

class FundFlowRepository:
    """
    資金流向資料訪問層：
    負責透過 FinMind 取得三大法人淨買賣超數據。
    處理 API 連線異常與空資料防呆。
    """
    
    @staticmethod
    def _fetch_single_stock(dl, stock_id: str, date_str: str) -> Optional[pd.DataFrame]:
        try:
            df = dl.taiwan_stock_institutional_investors(
                stock_id=stock_id,
                start_date=date_str,
                end_date=date_str
            )
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        return None

    @staticmethod
    def get_institutional_buy_sell(date_str: str) -> Optional[pd.DataFrame]:
        """
        取得指定日期的三大法人買賣超明細 (限 SECTOR_LIST 中的股票)
        回傳 DataFrame 包含: stock_id, buy, sell, name
        若無資料回傳 None
        """
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            
            # 從 SECTOR_LIST 提取所有股票代號 (去除 .TW)
            all_stocks = set()
            for stocks in SECTOR_LIST.values():
                for s in stocks:
                    clean_id = s.replace(".TW", "").replace(".tw", "")
                    all_stocks.add(clean_id)
                    
            all_stocks = list(all_stocks)
            if not all_stocks:
                return None

            results = []
            # 平行抓取，避免單個 API 呼叫太慢。限制 worker 數量避免被 API 阻擋
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(FundFlowRepository._fetch_single_stock, dl, sid, date_str): sid for sid in all_stocks}
                for future in concurrent.futures.as_completed(futures):
                    df = future.result()
                    if df is not None:
                        results.append(df)
            
            if not results:
                return None
                
            combined_df = pd.concat(results, ignore_index=True)
            return combined_df
            
        except ImportError:
            logger.error("FinMind is not installed.")
            return None
        except Exception as e:
            logger.error(f"Error fetching institutional data: {e}")
            return None
            
    @staticmethod
    def get_latest_trading_date() -> str:
        """
        推算最近的一個交易日。
        透過查詢 2330 過去 10 天的資料，找到 API 實際有資料的最新日期。
        若查詢失敗，則依時間推算。
        """
        today = datetime.datetime.now()
        start_date = today - datetime.timedelta(days=10)
        
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            df = dl.taiwan_stock_institutional_investors(
                stock_id="2330",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=today.strftime("%Y-%m-%d")
            )
            if df is not None and not df.empty and 'date' in df.columns:
                return str(df['date'].max())
        except Exception as e:
            logger.debug(f"Failed to fetch real latest date, fallback to heuristic: {e}")

        # Fallback heuristic
        if today.hour < 15:
            target_date = today - datetime.timedelta(days=1)
        else:
            target_date = today
            
        if target_date.weekday() == 5: # Saturday
            target_date = target_date - datetime.timedelta(days=1)
        elif target_date.weekday() == 6: # Sunday
            target_date = target_date - datetime.timedelta(days=2)
            
        return target_date.strftime("%Y-%m-%d")
