# services/risk_service.py
import pandas as pd
from typing import Optional
from core.models import RiskAssessment
from core.constants import PositionLevel, POSITION_ORDER, ATR_STOP_MULTIPLIER, RISK_PCT_LIMIT

class RiskService:
    """風險與部位控制邏輯層"""
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """計算 Average True Range (ATR)"""
        # 防呆：資料筆數不足
        if df is None or len(df) <= period:
            return None
            
        try:
            temp_df = df.copy()
            # True Range = max(High - Low, abs(High - prev_Close), abs(Low - prev_Close))
            temp_df['prev_Close'] = temp_df['Close'].shift(1)
            temp_df['tr_1'] = temp_df['High'] - temp_df['Low']
            temp_df['tr_2'] = abs(temp_df['High'] - temp_df['prev_Close'])
            temp_df['tr_3'] = abs(temp_df['Low'] - temp_df['prev_Close'])
            
            # 使用 numpy / pandas 向量化計算，取代舊版的逐行處理提高效率
            temp_df['TR'] = temp_df[['tr_1', 'tr_2', 'tr_3']].max(axis=1)
            atr_series = temp_df['TR'].rolling(window=period).mean()
            return float(atr_series.iloc[-1])
        except Exception:
            return None

    @staticmethod
    def get_volatility_flag(atr: float, close: float) -> str:
        """根據 ATR / Close 比例判斷市場波動程度"""
        # 防呆
        if atr is None or close is None or close <= 0:
            return "Unknown"
            
        ratio = atr / close
        if ratio > 0.05:  # 日震幅 > 5% 或 停損範圍大於 7.5%
            return "Extreme"
        elif ratio > 0.03: # 日震幅 > 3% 或 停損範圍大於 4.5%
            return "High"
        else:
            return "Normal"

    @staticmethod
    def adjust_position_down(current_level: PositionLevel) -> PositionLevel:
        """將倉位等級往下調整一級"""
        if current_level == PositionLevel.NO_POSITION:
            return PositionLevel.NO_POSITION
            
        idx = POSITION_ORDER.index(current_level)
        if idx > 0:
            return POSITION_ORDER[idx - 1]
        return PositionLevel.NO_POSITION

    @staticmethod
    def evaluate_risk(df: pd.DataFrame, current_price: float, initial_position: PositionLevel = PositionLevel.FULL) -> RiskAssessment:
        """
        全面評估標的風險，結合波動率動態降倉
        回傳 RiskAssessment DTO
        """
        # 如果無法計算 ATR 或拿到空資料
        atr = RiskService.calculate_atr(df)
        if atr is None or current_price is None or current_price <= 0:
            return RiskAssessment(
                atr=0.0,
                volatility_flag="Unknown",
                stop_loss_price=0.0,
                position_level=PositionLevel.NO_POSITION,
                risk_pct=0.0
            )

        flag = RiskService.get_volatility_flag(atr, current_price)
        final_position = initial_position
        
        # 波動太大，主動降倉一級
        if flag == "Extreme":
            final_position = RiskService.adjust_position_down(final_position)

        # 停損價格計算（基於 ATR_STOP_MULTIPLIER）
        stop_price = current_price - (atr * ATR_STOP_MULTIPLIER)
        
        # 計算帳面風險百分比 (買入價到停損價的距離)
        risk_pct = (current_price - stop_price) / current_price

        # 安全防護：如果單筆交易風險超過全域上限 RISK_PCT_LIMIT (預設 2%)
        # 再次強制降倉
        if risk_pct > RISK_PCT_LIMIT and final_position != PositionLevel.NO_POSITION:
            final_position = RiskService.adjust_position_down(final_position)

        return RiskAssessment(
            atr=atr,
            volatility_flag=flag,
            stop_loss_price=stop_price,
            position_level=final_position,
            risk_pct=risk_pct
        )
