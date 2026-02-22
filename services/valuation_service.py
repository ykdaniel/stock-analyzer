# services/valuation_service.py
from typing import Optional
from core.models import ValuationRequest, ValuationResponse
from core.constants import PE_EXPENSIVE_THRESHOLD, PE_REASONABLE_BASE, PE_GROWTH_MULTIPLIER

class ValuationService:
    """估值與財務健康度邏輯層"""
    
    @staticmethod
    def get_reasonable_pe(yoy_growth: Optional[float]) -> float:
        """動態計算合理 PE 倍數"""
        if yoy_growth is not None and yoy_growth > 30:
            return float(PE_GROWTH_MULTIPLIER)
        return float(PE_REASONABLE_BASE)

    @staticmethod
    def get_valuation_status(request: ValuationRequest) -> ValuationResponse:
        """動態估值判斷"""
        
        # 1. 邊界檢查/防呆
        if request.pe is None or request.eps is None:
             return ValuationResponse(
                 status="unknown", 
                 warning=False, 
                 reason="本益比或 EPS 資料不足", 
                 reasonable_pe=PE_REASONABLE_BASE
             )
        
        # 若 PE 小於 0 可能是公司虧損
        if request.pe < 0:
            return ValuationResponse(
                 status="unknown", 
                 warning=True, 
                 reason="公司虧損中 (PE < 0)", 
                 reasonable_pe=PE_REASONABLE_BASE
             )

        reason = ""
        warning = False
        reasonable_pe = ValuationService.get_reasonable_pe(request.yoy_growth)

        # 2. 估值判斷邏輯
        if request.pe > PE_EXPENSIVE_THRESHOLD:
            status = "expensive"
            warning = True
            reason = f"PE ({request.pe:.1f}) > 絕對昂貴線 ({PE_EXPENSIVE_THRESHOLD})"
        elif request.pe > reasonable_pe:
            # 輔助判斷：如果成長率不錯，給予稍微寬容的理由
            if request.yoy_growth and request.yoy_growth > 20:
                 status = "reasonable"
                 reason = f"PE ({request.pe:.1f}) > 基本合理線，但成長率 ({request.yoy_growth:.1f}%) 強勁"
            else:
                 status = "expensive"
                 warning = True
                 reason = f"PE ({request.pe:.1f}) > 動態合理線 ({reasonable_pe:.1f})"
        elif request.pe < 15:
             status = "cheap"
             reason = f"PE ({request.pe:.1f}) < 15 倍，估值偏低"
        else:
            status = "reasonable"
            reason = f"PE ({request.pe:.1f}) 位於合理區間"

        return ValuationResponse(
            status=status,
            warning=warning,
            reason=reason,
            reasonable_pe=reasonable_pe
        )
