# services/fund_flow_service.py
import pandas as pd
from typing import List, Dict, Optional, Tuple
from core.models import SectorFlowReport, FundFlowDetail
from core.constants import SECTOR_LIST
from repository.fund_flow_repo import FundFlowRepository
from repository.market_data_repo import MarketDataRepository

class FundFlowService:
    """
    資金流向服務層：
    整合 FinMind 取回的法人買賣超資料與本地的 SECTOR_LIST。
    提供各板塊淨流入金額的聚合與排序。
    """
    
    @staticmethod
    def get_sector_fund_flow_report() -> Optional[List[SectorFlowReport]]:
        """
        取得「最近一個交易日」的各類股法人買賣超排行榜
        回傳已依總淨流入(Total Net Flow)降冪排序的 SectorFlowReport 列表。
        """
        # 1. 取得目標日期
        target_date = FundFlowRepository.get_latest_trading_date()
        
        # 2. 獲取資料
        df = FundFlowRepository.get_institutional_buy_sell(target_date)
        if df is None or df.empty:
            return None
            
        # 3. 資料前處理：計算各檔股票的三大法人「加總」淨買賣超
        # 注意: FinMind 回傳的資料可能包含外資、投信、自營商等多筆紀錄
        # 依照 stock_id 群組，將 buy - sell 進行加總
        df['net_amount'] = pd.to_numeric(df['buy'], errors='coerce').fillna(0) - pd.to_numeric(df['sell'], errors='coerce').fillna(0)
        
        # 按 stock_id 分組加總淨買賣超
        net_flow_by_stock = df.groupby('stock_id')['net_amount'].sum().to_dict()
        
        # 4. 依照 SECTOR_LIST 聚合板塊數據
        reports = []
        for sector_name, tickers_with_tw in SECTOR_LIST.items():
            total_flow = 0
            details = []
            
            for ticker_with_tw in tickers_with_tw:
                # 移除 .TW 後綴去匹配 FinMind
                clean_ticker = ticker_with_tw.replace(".TW", "").replace(".tw", "")
                
                net_buy_sell = int(net_flow_by_stock.get(clean_ticker, 0))
                
                if net_buy_sell != 0:
                    total_flow += net_buy_sell
                    details.append(FundFlowDetail(
                        code=ticker_with_tw,
                        name=MarketDataRepository.get_stock_display_name(clean_ticker),
                        net_buy_sell=net_buy_sell
                    ))
            
            # 若該板塊內有成分股交易紀錄，則加入報告中
            if details:
                # 排序細項：將該板塊內個股由多到空排序
                details.sort(key=lambda x: x.net_buy_sell, reverse=True)
                reports.append(SectorFlowReport(
                    sector_name=sector_name,
                    total_net_flow=int(total_flow),
                    details=details
                ))
                
        # 5. 板塊由多到空降冪排序
        reports.sort(key=lambda x: x.total_net_flow, reverse=True)
        return reports
    
    @staticmethod
    def get_sector_fund_flow_report_multi_days(days: int = 7) -> Tuple[Optional[List[SectorFlowReport]], int, str, str]:
        """
        取得「最近 N 個交易日累計」的各類股法人買賣超排行榜。
        回傳 (reports, actual_days, start_date, end_date)。
        """
        start_str, end_str = FundFlowRepository.get_trading_dates_range(days)
        df = FundFlowRepository.get_institutional_buy_sell_range(start_str, end_str)
        if df is None or df.empty:
            return None, 0, start_str, end_str

        df['net_amount'] = (
            pd.to_numeric(df['buy'], errors='coerce').fillna(0)
            - pd.to_numeric(df['sell'], errors='coerce').fillna(0)
        )

        # 取得實際有資料的最新 N 個交易日
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            available_dates = sorted(df['date'].unique(), reverse=True)
            actual_days = min(days, len(available_dates))
            cutoff_dates = set(available_dates[:actual_days])
            df = df[df['date'].isin(cutoff_dates)]
            real_start = str(available_dates[actual_days - 1].date()) if actual_days > 0 else start_str
            real_end = str(available_dates[0].date()) if actual_days > 0 else end_str
        else:
            actual_days = days
            real_start, real_end = start_str, end_str

        # 依 stock_id 跨日加總
        net_flow_by_stock = df.groupby('stock_id')['net_amount'].sum().to_dict()

        reports = []
        for sector_name, tickers_with_tw in SECTOR_LIST.items():
            total_flow = 0
            details = []

            for ticker_with_tw in tickers_with_tw:
                clean_ticker = ticker_with_tw.replace(".TW", "").replace(".tw", "")
                net_buy_sell = int(net_flow_by_stock.get(clean_ticker, 0))

                if net_buy_sell != 0:
                    total_flow += net_buy_sell
                    details.append(FundFlowDetail(
                        code=ticker_with_tw,
                        name=MarketDataRepository.get_stock_display_name(clean_ticker),
                        net_buy_sell=net_buy_sell
                    ))

            if details:
                details.sort(key=lambda x: x.net_buy_sell, reverse=True)
                reports.append(SectorFlowReport(
                    sector_name=sector_name,
                    total_net_flow=int(total_flow),
                    details=details
                ))

        reports.sort(key=lambda x: x.total_net_flow, reverse=True)
        return reports, actual_days, real_start, real_end

    @staticmethod
    def get_latest_date_available() -> str:
        return FundFlowRepository.get_latest_trading_date()
