# services/strategy_engine.py
import pandas as pd
from typing import Optional
from core.models import StrategySignal, ValuationRequest
from core.constants import PositionLevel
from repository.market_data_repo import MarketDataRepository
from services.valuation_service import ValuationService
from services.risk_service import RiskService

class StrategyEngine:
    """核心選股與策略引擎"""
    
    @staticmethod
    def advanced_quant_filter(symbol: str, df: pd.DataFrame, valuation_req: ValuationRequest) -> Optional[StrategySignal]:
        """
        改良版量化濾網 (AI Quant Filter V2)
        將原本 app.py 內建的龐大計算邏輯抽離。
        """
        if df is None or len(df) < 50:
            return None
            
        try:
            # 取得最新一筆與前一日資料
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 準備計算指標
            close = latest['Close']
            volume = latest['Volume']
            ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            ma50 = df['Close'].rolling(window=50).mean().iloc[-1]
            
            # --- 1. 估值防護 ---
            val_resp = ValuationService.get_valuation_status(valuation_req)
            if val_resp.warning:
                # 估值過高，直接過濾 (或給予警告不買進)
                return StrategySignal(
                    signal="WAIT",
                    mode="N/A",
                    market_regime="N/A",
                    reasons=[f"估值警示: {val_resp.reason}"],
                    valuation_warning=True
                )
            
            # --- 2. 風險評估 ---
            risk_assess = RiskService.evaluate_risk(df, close)
            
            # --- 3. 趨勢與型態判定 ---
            trend_up = close > ma20 and ma20 > ma50
            volume_burst = volume > df['Volume'].rolling(window=5).mean().iloc[-1] * 1.5
            
            signal_type = "WAIT"
            mode = "Neutral"
            reasons = []
            
            if trend_up:
                mode = "Trend Following"
                if volume_burst:
                    signal_type = "BUY"
                    reasons.append("價量齊揚，突破均線糾結")
                else:
                    signal_type = "HOLD"
                    reasons.append("多頭排列，但量能未放大")
            elif close < ma50:
                mode = "Bearish"
                signal_type = "WAIT"
                reasons.append("股價跌破季線，趨勢偏空")
            else:
                mode = "Stock Picking"
                signal_type = "WAIT"
                reasons.append("區間震盪，無明顯趨勢")
                
            # 若 ATR 波動過大，覆寫買進訊號
            if risk_assess.volatility_flag == "Extreme" and signal_type == "BUY":
                signal_type = "WAIT"
                reasons.append("波動率過高 (Extreme)，暫停買進降低風險")
                
            return StrategySignal(
                signal=signal_type,
                mode=mode,
                market_regime="Up" if trend_up else ("Down" if close < ma50 else "Sideways"),
                entry_price=close if signal_type == "BUY" else None,
                stop_loss_price=risk_assess.stop_loss_price,
                reasons=reasons,
                valuation_warning=val_resp.warning
            )
            
        except Exception as e:
            return StrategySignal(
                signal="ERROR",
                mode="N/A",
                market_regime="N/A",
                reasons=[f"策略運算錯誤: {str(e)}"],
                valuation_warning=False
            )
            
    @staticmethod
    def calculate_tradelog(code: str, buy_price: float, current_price: float, qty: int, fee_discount: float = 1.0) -> dict:
        """
        計算單筆交易損益與手續費
        """
        try:
            if buy_price <= 0:
                 return {"status": "Error", "reason": "購入價格異常 (<= 0)"}
                 
            # 買入成本
            cost_basis = round(buy_price * qty)
            buy_fee = round(cost_basis * 0.001425 * fee_discount)
            buy_fee = max(20, buy_fee)
            total_buy_cost = cost_basis + buy_fee
            
            # 賣出價值
            market_value = round(current_price * qty)
            sell_fee = round(market_value * 0.001425 * fee_discount)
            sell_fee = max(20, sell_fee)
            tax = round(market_value * 0.003)
            total_sell_recovery = market_value - sell_fee - tax
            
            net_profit = total_sell_recovery - total_buy_cost
            roi_pct = (net_profit / total_buy_cost) * 100 if total_buy_cost > 0 else 0
            
            return {
                "code": MarketDataRepository.normalize_stock_id(code),
                "buy_price": buy_price,
                "current_price": current_price,
                "qty": qty,
                "cost_basis": cost_basis,
                "buy_fee": buy_fee,
                "market_value": market_value,
                "sell_fee": sell_fee,
                "tax": tax,
                "total_cost": total_buy_cost,
                "net_value": total_sell_recovery,
                "unrealized_profit": net_profit,
                "profit_pct": round(roi_pct, 2),
                "status": "Win" if net_profit > 0 else "Loss"
            }
        except Exception as e:
             return {"status": "Error", "reason": f"計算錯誤: {str(e)}"}
