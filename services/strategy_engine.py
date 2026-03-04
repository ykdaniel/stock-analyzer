import pandas as pd
from typing import Optional, Dict, Any, List
from core.models import StrategySignal, ValuationRequest
from core.constants import PositionLevel
from repository.market_data_repo import MarketDataRepository
from services.valuation_service import ValuationService
from services.risk_service import RiskService

class StrategyEngine:
    """核心選股與策略引擎 (已還原完整三層架構)"""
    
    @staticmethod
    def market_regime_gate(df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or df.empty or len(df) < 30:
            return {"allow_long": False, "regime": "UNKNOWN", "reason": "資料不足，無法判斷"}
        
        curr = df.iloc[-1]
        close = float(curr['Close'])
        ma20 = float(curr.get('MA20', float('nan')))
        ma60 = float(curr.get('MA60', float('nan')))
        ma60_slope = float(df['MA60'].diff().tail(5).mean()) if 'MA60' in df.columns else 0.0
        
        if close >= ma60 and ma20 >= ma60 and ma60_slope > 0:
            return {"allow_long": True, "regime": "BULL", "reason": "多頭市場"}
        elif close >= ma60:
            return {"allow_long": True, "regime": "NEUTRAL", "reason": "盤整市場"}
        else:
            return {"allow_long": False, "regime": "BEAR", "reason": "空頭市場"}

    @staticmethod
    def select_strategy_mode(df: pd.DataFrame, market_regime: str) -> Dict[str, Any]:
        if df is None or df.empty or len(df) < 30:
            return {"mode": "Momentum", "reason": "順勢操作 (MA5/10 核心)"}
            
        curr = df.iloc[-1]
        close = float(curr['Close'])
        ma20 = float(curr.get('MA20', float('nan')))
        ma60 = float(curr.get('MA60', float('nan')))
        ma60_slope = float(df['MA60'].diff().tail(5).mean()) if 'MA60' in df.columns else 0.0

        price_above_ma20 = close > ma20
        price_above_ma60 = close > ma60
        ma20_above_ma60 = ma20 > ma60
        ma60_rising = ma60_slope > 0
        is_low_consolidation = market_regime == "NEUTRAL" and abs(close - ma60) / ma60 < 0.05
        
        # 移除嚴格的市場結構阻擋，原本的 A/B Mode 保留為輔助參考
        if price_above_ma20 and price_above_ma60 and ma20_above_ma60 and ma60_rising and not is_low_consolidation:
            return {"mode": "Trend", "reason": "多頭排列"}
            
        def prev_n_days(series, n):
            if series is None or len(series) < n + 1: return series.iloc[0:0]
            return series.iloc[-(n + 1):-1]
            
        price_near_ma20 = abs(close - ma20) / ma20 <= 0.05 if ma20 > 0 else False
        price_near_ma60 = abs(close - ma60) / ma60 <= 0.05 if ma60 > 0 else False
        
        prev10_low = prev_n_days(df['Low'], 10)
        recent_low_10 = float(prev10_low.min()) if not prev10_low.empty else float('nan')
        no_new_low = close >= recent_low_10 if not prev10_low.empty else True
        ma60_not_falling = ma60_slope >= 0
        
        if (price_near_ma20 or price_near_ma60) and no_new_low and ma60_not_falling:
            return {"mode": "Pullback", "reason": "均線有撐"}
            
        return {"mode": "Momentum", "reason": "順勢操作 (MA5/10 核心)"}

    @staticmethod
    def evaluate_stock(df: pd.DataFrame, market_regime: str, strategy_mode: str, 
                       valuation_req: ValuationRequest) -> StrategySignal:
        MAX_MA60_EXTENSION = 1.25
        ATR_BUFFER_PULLBACK = 0.5
        ATR_BUFFER_TREND = 1.0
        
        import math
        
        signal_data = StrategySignal(
            signal="NoTrade",
            mode=strategy_mode,
            market_regime=market_regime,
            reasons=["分析未完成"],
            exit_conditions=[],
            not_buy_reasons=[]
        )
        
        if df is None or df.empty or len(df) < 30:
            signal_data.reasons = ["資料不足"]
            return signal_data
            
        curr = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else curr
        close = float(curr['Close'])
        open_price = float(curr.get('Open', close))
        high = float(curr.get('High', close))
        low = float(curr.get('Low', close))
        ma5 = float(curr.get('MA5', float('nan')))
        ma10 = float(curr.get('MA10', float('nan')))
        ma20 = float(curr.get('MA20', float('nan')))
        ma60 = float(curr.get('MA60', float('nan')))
        vol = float(curr.get('Volume', 0))
        vol_ma20 = float(curr.get('Vol_MA20', 0))
        rsi_curr = float(curr.get('RSI', float('nan')))
        k = float(curr.get('K', float('nan')))
        d = float(curr.get('D', float('nan')))
        prev_k = float(prev.get('K', float('nan')))
        prev_d = float(prev.get('D', float('nan')))
        ma60_slope = float(df['MA60'].diff().tail(5).mean()) if 'MA60' in df.columns else 0.0
        ma20_slope = float(df['MA20'].diff().tail(5).mean()) if 'MA20' in df.columns else 0.0
        atr = RiskService.calculate_atr(df)
        swing_low_10 = float(curr.get('Swing_Low_10', float('nan')))
        
        if vol_ma20 <= 0:
            signal_data.reasons = ["流動性不足"]
            signal_data.not_buy_reasons.append("流動性不足")
            return signal_data
            
        ma60_extension_ratio = close / ma60 if ma60 > 0 else 1.0
        is_overextended = ma60_extension_ratio > MAX_MA60_EXTENSION
        
        can_buy = True
        
        # 取得輔助參數: 估值、波動、KDJ
        volatility_flag = RiskService.get_volatility_flag(atr, close) if atr else "Normal"
        val_resp = ValuationService.get_valuation_status(valuation_req)
        valuation_warning = val_resp.warning
        signal_data.valuation_warning = valuation_warning
        
        if volatility_flag == "Extreme":
            can_buy = False
            signal_data.not_buy_reasons.append(f"⛔ 買進禁止：近期波動度極端 (Extreme)")
            
        # 判斷 KDJ 狀態
        kdj_ideal = False
        kdj_reason = ""
        if not pd.isna(k) and not pd.isna(d):
            if k < d and d < prev_d:
                can_buy = False
                kdj_reason = "⛔ 買進禁止：KDJ 高檔轉弱 (死叉)"
                signal_data.not_buy_reasons.append(kdj_reason)
            elif d <= 40 and k >= d:
                kdj_ideal = True
                kdj_reason = "💡 KDJ 低檔金叉 (有利回檔)"
            else:
                kdj_reason = f"💡 KDJ 狀態 K={k:.1f}, D={d:.1f}"
        if kdj_reason and can_buy:
            signal_data.reasons.append(kdj_reason)

        if is_overextended:
            can_buy = False
            signal_data.not_buy_reasons.append("⛔ 買進禁止：股價乖離率偏高 (>25%)")
            
        if market_regime == "BEAR":
            can_buy = False
            signal_data.not_buy_reasons.append("⛔ 買進禁止：長線結構偏空 (BEAR)")
            
        # 計算短均線斜率防雙巴
        ma5_slope = float(df['MA5'].diff().tail(3).mean()) if 'MA5' in df.columns else 0.0
        ma10_slope = float(df['MA10'].diff().tail(3).mean()) if 'MA10' in df.columns else 0.0
        
        # =========== 核心 MA5 / MA10 動能策略 ===========
        buy = False
        watch = False
        
        # 1. 第一優先出脫條件
        exit_half = close < ma5
        exit_all = close < ma10
        
        if exit_all:
            signal_data.exit_conditions.append("跌破 MA10 (全數出場)")
        elif exit_half:
            signal_data.exit_conditions.append("跌破 MA5 (減碼 50%)")
            
        ma_aligned = ma5 > ma10
        slopes_up = ma5_slope > 0 and ma10_slope > 0
        close_above_ma5 = close > ma5
        not_chasing_top = close <= ma5 * 1.05  # 不追離 MA5 超過 5% 的短線過熱股
        
        if ma_aligned and close_above_ma5:
            if slopes_up and not_chasing_top and can_buy:
                # 核心無腦買進條件：MA5/MA10 多頭排列、站穩MA5、均線上揚、未過熱，且通過所有防護網
                buy = True
                signal_data.reasons.insert(0, "⭐ 核心觸發：MA5 > MA10 且 均線上揚 (動能確認)")
                if vol >= vol_ma20 * 1.5:
                    signal_data.reasons.append("⭐ 價量配合：本日爆量發動 (>1.5倍均量)")
            elif not can_buy:
                watch = True
                signal_data.reasons.insert(0, "👀 核心觀察：MA5動能到位，但觸發防護網 (請見不買原因)")
            elif not slopes_up:
                watch = True
                signal_data.reasons.insert(0, "👀 核心觀察：MA5 > MA10，但均線下彎或走平 (防假突破雙巴)")
            elif not not_chasing_top:
                watch = True
                signal_data.reasons.insert(0, f"👀 核心觀察：多頭強勢，但短線乖離率過高 (偏離MA5 > 5%)，等拉回")
        elif ma_aligned and not close_above_ma5:
            # 觀察狀態：多頭排列但跌破 5日線 (減碼中)
            watch = True
            signal_data.reasons.insert(0, "👀 核心觀察：MA5 > MA10，但股價跌破 MA5，醞釀中")
        else:
            signal_data.not_buy_reasons.append("⭐ 核心不過：未滿足 MA5 > MA10 多頭排列")
            
        # 保留原本的其他離場警示為輔助
        if close < ma20: signal_data.exit_conditions.append("跌破 MA20")
        if ma20_slope < 0: signal_data.exit_conditions.append("MA20下彎")
        if not pd.isna(rsi_curr) and rsi_curr > 80: signal_data.exit_conditions.append("過熱: RSI>80")
            
        pos_level = PositionLevel.NO_POSITION
        if buy:
            pos_level = PositionLevel.HEAVY if (volatility_flag != "Extreme" and not valuation_warning) else PositionLevel.MEDIUM
                
        stop_loss_price = None
        stop_loss_method = None
        risk_pct = None
        if buy or watch:
            # 動能策略停損價預設設於 MA10 或 MA5 取低者
            stop_loss_price = min(ma10, ma5) if not pd.isna(ma10) and not pd.isna(ma5) else ma10
            stop_loss_method = "跌破 MA10 系統停損"
            if stop_loss_price and close > 0:
                risk_pct = (close - stop_loss_price) / close * 100
                
        if exit_all:
            signal_data.signal = "Exit"
        elif exit_half:
            # 跌破 MA5 未破 MA10，亮 Exit 提醒減碼，或 Watch
            signal_data.signal = "Exit"
        elif buy: signal_data.signal = "Buy"
        elif watch: signal_data.signal = "Watch"
        else: signal_data.signal = "NoTrade"
        
        # Confidence logic simplified
        conf = 0
        if buy: conf = 90
        elif watch: conf = 50
        elif signal_data.signal == "Exit": conf = 80
        
        signal_data.position_level = pos_level
        signal_data.entry_price = close if buy else None
        signal_data.stop_loss_price = round(stop_loss_price, 2) if stop_loss_price else None
        signal_data.atr = round(atr, 2) if atr else None
        signal_data.stop_loss_method = stop_loss_method
        signal_data.risk_pct = round(risk_pct, 2) if risk_pct else None
        signal_data.watch = watch
        signal_data.buy = buy
        signal_data.confidence = conf
        
        return signal_data

    @staticmethod
    def advanced_quant_filter(df: pd.DataFrame, valuation_req: ValuationRequest) -> StrategySignal:
        gate = StrategyEngine.market_regime_gate(df)
        mode_res = StrategyEngine.select_strategy_mode(df, gate['regime'])
        
        if not gate['allow_long'] or mode_res['mode'] == 'NoTrade':
            return StrategySignal(
                signal="NoTrade",
                mode=mode_res['mode'],
                market_regime=gate['regime'],
                reasons=[gate['reason'] if not gate['allow_long'] else mode_res['reason']]
            )
            
        return StrategyEngine.evaluate_stock(df, gate['regime'], mode_res['mode'], valuation_req)

    @staticmethod
    def calculate_tradelog(code: str, buy_price: float, current_price: float, qty: int, fee_discount: float = 1.0) -> dict:
        try:
            if buy_price <= 0:
                 return {"status": "Error", "reason": "購入價格異常 (<= 0)"}
            cost_basis = round(buy_price * qty)
            buy_fee = max(20, round(cost_basis * 0.001425 * fee_discount))
            total_buy_cost = cost_basis + buy_fee
            market_value = round(current_price * qty)
            sell_fee = max(20, round(market_value * 0.001425 * fee_discount))
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
