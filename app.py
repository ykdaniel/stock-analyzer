"""
AI 量化戰情室 - 台股分析系統

【策略引擎升級版本 v2.0】

修復日期：2026-02-04
升級內容：
  1. 修正邏輯鎖死問題
     - NEUTRAL 市場不再直接 NoTrade，允許 Stock Picking 模式
     - Buy 不被 Watch 狀態硬鎖（Buy = Trend_Buy OR Pullback_Buy）
  
  2. KDJ 規則依 Mode 切換
     - Pullback 模式：D <= 40 AND K >= D（低檔買入）
     - Trend 模式：NOT (K < D AND D falling)（避免高檔死叉）
  
  3. 補齊 Exit/Sell 條件
     - Exit_Defensive: Close < MA20 OR Close < MA10
     - Exit_Trend_End: MA20_slope < 0 OR MA20 < MA60
     - Exit_Overheat: RSI > 80 OR KDJ 高檔死叉
  
  4. 新增倉位建議（Position Sizing）
     - 輸出等級：No_Position, Light, Medium, Heavy, Full
     - 依市場狀態與模式決定基礎倉位
     - 估值警示/高波動會自動降倉
  
  5. 動態停損位計算（ATR 緩衝）
     - Pullback 模式：Swing_Low - ATR * 0.5
     - Trend 模式：MA20 - ATR * 1.0
     - ATR 快取避免重複計算
     - ATR 異常波動防呆（上限鉗制、比例檢查）
  
  6. 動態估值與 EPS 警示
     - EPS > 20 僅作警示，不否決 Buy
     - PE > 40 一律視為「昂貴」
     - 動態合理 PE 連動成長率
  
  7. 輸出完整交易卡片
     - signal, mode, market_regime, position_level
     - entry_price, stop_loss_price, atr, risk_pct
     - exit_conditions, not_buy_reasons, valuation_warning

歷史修復：
  2026-01-24: 移除 6 個重複函數定義，語法驗證通過
"""


from core.constants import (
    SectorType, PositionLevel, POSITION_ORDER,
    PE_EXPENSIVE_THRESHOLD, PE_REASONABLE_BASE, PE_GROWTH_MULTIPLIER,
    SECTOR_LIST, STOCK_DB, BAD_TICKERS, EXTRA_SECTORS_FOR_DROPDOWN,
)
from core.models import ValuationRequest, RiskAssessment, StrategySignal
from repository.market_data_repo import MarketDataRepository
from services.valuation_service import ValuationService
from services.risk_service import RiskService
from services.strategy_engine import StrategyEngine
from services.fund_flow_service import FundFlowService

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import os
import re
import json
import logging

logger = logging.getLogger(__name__)

# ==========================================
# 0. 環境檢查與設定
# ==========================================
st.set_page_config(layout="wide", page_title="AI 量化戰情室 (最終旗艦版)")

# 檢查 FinMind 是否安裝
try:
    from FinMind.data import DataLoader
    FINMIND_AVAILABLE = True
except ImportError:
    DataLoader = None
    FINMIND_AVAILABLE = False
    st.error("❌ 未安裝 FinMind 套件。請執行 `pip install FinMind` 以啟用籌碼功能。")

# 顏色設定 (Antigravity 專業版：旗艦紅綠配色)
COLOR_UP = '#FF4B4B'    # 鮮豔紅 (上漲)
COLOR_DOWN = '#00D964'  # 鮮豔綠 (下跌)

# ==========================================
# ATR 計算與快取模組
# ==========================================
# NOTE: ATR 是「尺度」，用於計算停損緩衝，不是「結構」判斷依據


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    計算 Average True Range (ATR)
    
    ATR = Rolling Mean of True Range
    True Range = max(High - Low, abs(High - prev_Close), abs(Low - prev_Close))
    """
    if df is None or df.empty or len(df) < period:
        return pd.Series(dtype=float)
    
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(period).mean()
    return atr


# ==========================================
# 估值參數設定（Valuation Settings）
# ==========================================
# NOTE: EPS > EPS_HIGH_THRESHOLD 且 YoY Growth < 20% → 輸出估值警示


def get_valuation_status(pe: Optional[float], eps: Optional[float], yoy_growth: Optional[float]) -> dict:
    resp = ValuationService.get_valuation_status(ValuationRequest(pe=pe, eps=eps, yoy_growth=yoy_growth))
    return {"status": resp.status, "warning": resp.warning, "reason": resp.reason, "reasonable_pe": resp.reasonable_pe}

# --- 全域 CSS 樣式 ---
st.markdown("""
    <style>
    /* 強制所有 Dataframe 表頭 (TH) 置中 */
    div.stDataFrame th {
        text-align: center !important;
        vertical-align: middle !important;
    }
    [data-testid="stHeaderRowCell"] {
        text-align: center !important;
        vertical-align: middle !important;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    /* 強制內容置中或靠右 (由 Pandas Styler 輔助) */
    
    /* 輸入框底色改為淺灰色 */
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="base-input"] {
        background-color: #f0f2f6 !important;
        border-radius: 4px;
    }
    .stTextInput input, .stNumberInput input, .stDateInput input {
        background-color: transparent !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 損益計算工具 ---
def calculate_tradelog(code, buy_price, current_price, qty, fee_discount=1.0):
    return StrategyEngine.calculate_tradelog(code, buy_price, current_price, qty, fee_discount)

# ==========================================
# 1. 資料庫定義（統一由 core/constants.py 提供）
# ==========================================
# SectorType, STOCK_DB, SECTOR_LIST, BAD_TICKERS, EXTRA_SECTORS_FOR_DROPDOWN
# 已於頂部 import，此處不再重複定義。

# ==========================================
# 台灣50 成分股（近似版）與「排除金融」版本
# ==========================================
# 說明：
# - 這裡使用的是依照 0050 成分股整理出的常見台灣50成分股近似名單。
# - 主要成分幾乎全數涵蓋，但指數成分會隨時間微調，若未來官方名單有變更，可在此列表增減。
# - `TAIWAN50_EX_FIN_TICKERS` 會排除金融股 (28xx.TW / 5880.TW 等)，供「台灣50 (排除金融)」頁面使用。
TAIWAN50_TICKERS = [
    "2330.TW",  # 台積電
    "2317.TW",  # 鴻海
    "2454.TW",  # 聯發科
    "2308.TW",  # 台達電
    "2382.TW",  # 廣達
    "2303.TW",  # 聯電
    "3711.TW",  # 日月光投控
    "2311.TW",  # 日月光（備用，視版本而定）
    "2301.TW",  # 光寶科
    "2379.TW",  # 瑞昱
    "3034.TW",  # 聯詠
    "3035.TW",  # 智原
    "6669.TW",  # 緯穎
    "2383.TW",  # 台光電
    "2327.TW",  # 國巨
    "2412.TW",  # 中華電
    "4904.TW",  # 遠傳
    "3045.TW",  # 台灣大
    "2305.TW",  # 全友
    "1301.TW",  # 台塑
    "1303.TW",  # 南亞
    "1326.TW",  # 台化
    "6505.TW",  # 台塑化
    "2002.TW",  # 中鋼
    "2603.TW",  # 長榮
    "2609.TW",  # 陽明
    "2615.TW",  # 萬海
    "2618.TW",  # 長榮航
    "1513.TW",  # 中興電
    "1519.TW",  # 華城
    "1503.TW",  # 士電
    "1605.TW",  # 華新
    "1101.TW",  # 台泥
    "1216.TW",  # 統一
    "2912.TW",  # 統一超
    "2881.TW",  # 富邦金
    "2882.TW",  # 國泰金
    "2891.TW",  # 中信金
    "2886.TW",  # 兆豐金
    "2884.TW",  # 玉山金
    "2892.TW",  # 第一金
    "2880.TW",  # 華南金
    "2885.TW",  # 元大金
    "2883.TW",  # 開發金
    "2887.TW",  # 台新金
    "5871.TW",  # 中租-KY
    "5876.TW",  # 上海商銀
    "6269.TW",  # 台郡（部分版本）
    "2357.TW",  # 華碩
    "2376.TW",  # 技嘉
]

TAIWAN50_EX_FIN_TICKERS = [
    t for t in TAIWAN50_TICKERS
    if not (t.startswith("288") or t.startswith("289") or t in {"5871.TW", "5876.TW"})
]

# ==========================================
# AI 概念股清單
# ==========================================
# 說明：涵蓋 AI 伺服器供應鏈、散熱、CoWoS 先進封裝、ASIC、網通等 AI 相關概念股
AI_CONCEPT_TICKERS = [
    "2330.TW",  # 台積電 (AI晶片代工)
    "2454.TW",  # 聯發科 (AI晶片設計)
    "2382.TW",  # 廣達 (AI伺服器)
    "3231.TW",  # 緯創 (AI伺服器)
    "6669.TW",  # 緯穎 (雲端伺服器)
    "2317.TW",  # 鴻海 (AI伺服器代工)
    "3017.TW",  # 奇鋐 (AI散熱)
    "2345.TW",  # 智邦 (AI網通)
    "3661.TW",  # 世芯-KY (ASIC設計)
    "6415.TW",  # 矽力-KY (電源管理IC)
    "2379.TW",  # 瑞昱 (網通晶片)
    "3034.TW",  # 聯詠 (驅動IC/AI邊緣)
    "2376.TW",  # 技嘉 (AI伺服器/顯卡)
    "2357.TW",  # 華碩 (AI PC)
    "3443.TW",  # 創意 (ASIC設計服務)
    "2383.TW",  # 台光電 (CCL/AI伺服器)
    "3037.TW",  # 欣興 (ABF載板)
    "3711.TW",  # 日月光投控 (先進封裝)
    "2308.TW",  # 台達電 (電源/散熱)
    "6515.TW",  # 穎崴 (探針卡)
]


# SECTOR_LIST, BAD_TICKERS, EXTRA_SECTORS_FOR_DROPDOWN 已於頂部 import，此處不再定義。
# 補充 EXTRA_SECTORS 空槽位到 SECTOR_LIST
for s in EXTRA_SECTORS_FOR_DROPDOWN:
    if s not in SECTOR_LIST:
        SECTOR_LIST[s] = []

FULL_MARKET_DEMO = [c for c in STOCK_DB.keys() if c not in BAD_TICKERS]


@st.cache_data(ttl=86400, show_spinner=False)
def _build_twse_name_map() -> dict:
    """
    從 TWSE/TPEX 公開 API 抓取全台上市櫃股票名稱對照表，每天只抓一次。
    回傳 {中文名稱: 代號(.TW)} 的字典。
    """
    name_map = {}
    try:
        import requests
        # 上市
        r1 = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
            timeout=8
        )
        if r1.status_code == 200:
            for item in r1.json():
                code = item.get("Code", "")
                name = item.get("Name", "")
                if code and name:
                    name_map[name] = f"{code}.TW"
    except Exception:
        pass
    try:
        import requests
        # 上櫃
        r2 = requests.get(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
            timeout=8
        )
        if r2.status_code == 200:
            for item in r2.json():
                code = item.get("SecuritiesCompanyCode", "")
                name = item.get("CompanyAbbreviation", "")
                if code and name:
                    name_map[name] = f"{code}.TWO"
    except Exception:
        pass
    return name_map


def normalize_stock_id(code: str) -> str:
    """
    標準化股票代號：支援中文名稱反查，或自動補上 .TW 後綴並轉大寫

    範例：
    - "台積電" -> "2330.TW"
    - "台玻"   -> "1802.TW"  (動態查詢 TWSE)
    - "2330"   -> "2330.TW"
    - "2330.TW"-> "2330.TW"
    """
    try:
        if not code or not isinstance(code, str):
            return code
        s = code.strip()
        if s == '':
            return s

        # 1. 若含有中文，先嘗試名稱反查
        if not s.replace('.', '').isascii():
            # --- 1a. 查本地 STOCK_DB (快) ---
            matched_ticker = None
            for ticker, info in STOCK_DB.items():
                name = info.get('name', '')
                if s == name:
                    return ticker
                if s in name and not matched_ticker:
                    matched_ticker = ticker
            if matched_ticker:
                return matched_ticker

            # --- 1b. 查 TWSE 全市場對照表 (慢，但包含全市場) ---
            twse_map = _build_twse_name_map()
            # 完全比對
            if s in twse_map:
                return twse_map[s]
            # 部分比對
            for name, ticker in twse_map.items():
                if s in name:
                    return ticker

        # 2. 原始代號邏輯
        if '.' in s:
            parts = s.split('.', 1)
            return parts[0].upper() + '.' + parts[1].upper()
        return s.upper() + '.TW'
    except Exception:
        return code

# --- 全域樣式函式 ---
def apply_table_style(df):
    """
    統一對 DataFrame 套用樣式：
    1. 標題置中
    2. 數值靠右
    3. 指定欄位千分位與小數點格式
    4. 損益欄位顏色 (紅漲綠跌)
    """
    # 顏色設定
    def color_profit(val):
        if not isinstance(val, (int, float)): return ''
        # 紅漲(正) 綠跌(負)
        color = '#FF0000' if val > 0 else '#009900' if val < 0 else 'black'
        return f'color: {color}; font-weight: bold;'
    
    # 建立 Styler
    styler = df.style
    
    # 1. 數值格式 (千分位)
    format_dict = {}
    
    # (A) 金額與股數：整數顯示
    amount_cols = ['股數', '成本(含費)', '市值(扣費)', '未實現損益(元)', '已實現淨損益', '成交量', '量能', '前日買賣超', '今日買賣超']
    for col in amount_cols:
        if col in df.columns:
            format_dict[col] = "{:,.0f}"

    # (B) 股價：小數點後兩位
    price_cols = ['買入價', '買入單價', '賣出單價', '最新價', '收盤價', '開盤價', '最高價', '最低價', 'MA5', 'MA10', 'MA20', 'MA60']
    for col in price_cols:
        if col in df.columns:
            format_dict[col] = "{:,.2f}"
    
    # (C) 百分比格式
    pct_cols = ['未實現損益(%)', '報酬率(%)', '漲跌幅']
    for col in pct_cols:
            if col in df.columns:
                format_dict[col] = "{:.2f}%"

    styler = styler.format(format_dict)
    
    # 2. 顏色 (損益欄位)
    profit_cols = ['未實現損益(元)', '未實現損益(%)', '已實現淨損益', '報酬率(%)', '漲跌幅']
    subset_cols = [c for c in profit_cols if c in df.columns]
    styler = styler.applymap(color_profit, subset=subset_cols)
    
    # 3. 對齊 (標題置中，數值靠右)
    styler = styler.set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('vertical-align', 'middle')]},
        {'selector': 'td', 'props': [('text-align', 'right')]}
    ])
    
    return styler

@st.cache_data(ttl=86400)
def get_stock_display_name(code: str) -> str:
    """
    取得股票顯示名稱（優先中文）：
    1. 先從內建 STOCK_DB 對照表（中文）
    2. 再從 FinMind taiwan_stock_info 取得中文名稱
    3. 若都沒有，最後才用 yfinance 英文名稱
    """
    try:
        if not code:
            return ""

        # 1) 內建對照表
        if code in STOCK_DB:
            return STOCK_DB[code].get("name", code)

        # 2) FinMind 中文名稱
        if FINMIND_AVAILABLE:
            try:
                df_info = SectorProvider.get_taiwan_stock_info()
                if df_info is not None and not df_info.empty:
                    clean = code.split('.')[0]
                    row = df_info[df_info['stock_id'] == clean]
                    if not row.empty:
                        name_tw = row.iloc[0].get('stock_name')
                        if isinstance(name_tw, str) and name_tw.strip():
                            return name_tw.strip()
            except Exception:
                pass

        # 3) yfinance 英文名稱（最後備援）
        try:
            ticker = yf.Ticker(code)
            info = getattr(ticker, "info", {}) or {}
            for key in ["shortName", "longName", "name"]:
                val = info.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        except Exception:
            pass

        return code
    except Exception:
        return code

# 觀察清單檔案路徑（共用）
DATA_DIR = os.path.abspath(os.path.dirname(__file__))
WATCHLIST_FILE = os.path.join(DATA_DIR, 'watchlist.json')

def load_watchlist() -> List[Dict[str, str]]:
    """從文件加載觀察清單。"""
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.debug("load_watchlist error: %s", e)
    return []

def save_watchlist(data: List[Dict[str, str]]) -> bool:
    """將觀察清單保存到文件。成功回傳 True。"""
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.debug("save_watchlist error: %s", e)
        if 'st' in dir():
            st.error(f"保存觀察清單失敗：{e}")
        return False

def add_to_watchlist(code: str, name: str):
    """將股票加入觀察清單（避免重複），並保存到文件。"""
    wl = load_watchlist()
    if not any(item.get('code') == code for item in wl):
        wl.append({'code': code, 'name': name})
        if save_watchlist(wl):
            st.session_state['watchlist'] = wl
        else:
            st.session_state['watchlist'] = wl  # 仍更新 session，僅寫檔失敗

# 若某些類股為空，為下拉選單提供代表性成分（僅作為掃描示例，不修改 `STOCK_DB`）
EXTRA_REPRESENTATIVES = {
    "生技/醫療": ["3034.TW"],
    "綠能/再生能源": ["1216.TW"],
    "半導體設備": ["3711.TW"],
    "電動車/電池": ["2207.TW"],
    "軟體/雲端服務": ["2345.TW"],
    "光電/面板": ["2383.TW"],
    "消費性電子": ["2357.TW"],
    "半導體材料": ["6415.TW"],
    "不動產/建設": ["1216.TW"],
    "食品/日用品": ["2912.TW"],
    "航太/國防": ["2603.TW"],
}
for sec, reps in EXTRA_REPRESENTATIVES.items():
    if sec in SECTOR_LIST and (not SECTOR_LIST[sec]):
        for r in reps:
            if r not in BAD_TICKERS and r not in SECTOR_LIST[sec]:
                SECTOR_LIST[sec].append(r)

# ==========================================
# 2. 資料模型 (DTO)
# ==========================================
@dataclass
class StockAnalysisResult:
    """股票分析結果資料類別"""
    stock_id: str
    score: int
    reasons: List[str]
    tech_df: pd.DataFrame
    fundamentals: Dict[str, Any]
    chips_df: Optional[pd.DataFrame] = None
    
    @property
    def status_summary(self) -> str:
        """生成狀態摘要"""
        return " / ".join(self.reasons) if self.reasons else "無符合項目"

# ==========================================
# 3. 資料提供者 (Data Providers)
# ==========================================
class SectorProvider:
    """負責處理類股與股票清單 (FinMind)"""
    
    @staticmethod
    @st.cache_data(ttl=86400) # 快取一天
    def get_taiwan_stock_info():
        if not FINMIND_AVAILABLE:
            return None
        try:
            dl = DataLoader()
            df = dl.taiwan_stock_info()
            return df
        except Exception as e:
            logger.debug("SectorProvider Error: %s", e)
            return None

    @staticmethod
    def get_sectors():
        """取得所有產業類別清單"""
        df = SectorProvider.get_taiwan_stock_info()
        if df is None: return []
        # 過濾掉空的與不需要的類別（含創新板/創新版及其他非核心板塊）
        EXCLUDED_SECTORS = {
            "創新板股票", "創新版股票",
            "運動休閒", "運動休閒類",
            "金融保險", "金融業",
            "鋼鐵工業",
            "大盤", "存託憑證",
            "居家生活", "居家生活類",
            "貿易百貨", "文化創意業",
            "觀光事業", "觀光餐旅",
            "農業科技業", "農業科技",
            "其他電子業", "其他電子類",
        }
        sectors = df['industry_category'].dropna().unique().tolist()
        return sorted([s for s in sectors if s and s not in EXCLUDED_SECTORS])

    @staticmethod
    def get_sector_stocks_info(sector_name):
        """取得指定類別的股票資訊 (ID -> Name Dict)"""
        df = SectorProvider.get_taiwan_stock_info()
        if df is None: return {}
        
        subset = df[df['industry_category'] == sector_name]
        # 建立 ID (.TW) -> Name 的對照表
        info_map = {}
        for _, row in subset.iterrows():
            sid = normalize_stock_id(row['stock_id'])
            info_map[sid] = row['stock_name']
        return info_map

class TechProvider:
    """負責處理技術與價格資料 (yfinance)"""
    
    @staticmethod
    def fetch_data(stock_id: str, start_date):
        """
        下載技術資料供指標與策略判斷使用
        
        說明：
        - 策略計算需要比 UI 起始日更長的歷史，用來供 MA60、RSI 等指標穩定收斂
        - 接收 UI 傳入的 start_date，但實際抓取區間會「往前多抓約 100 天」，同時最多回溯 5 年
        - yfinance 的 end 參數為「到但不含 end 當日」，因此會將 end 設為「明天」，避免漏掉今天
        """
        today = pd.Timestamp.today().normalize()
        base_end = today + pd.DateOffset(days=1)  # 避免漏抓今天

        # UI 給的分析起始日（若無，預設為 5 年前）
        try:
            user_start = pd.to_datetime(start_date).normalize() if start_date is not None else today - pd.DateOffset(years=5)
        except Exception:
            user_start = today - pd.DateOffset(years=5)

        # 為技術指標預留 100 天的緩衝區間
        buffered_start = user_start - pd.Timedelta(days=100)
        five_years_ago = today - pd.DateOffset(years=5)
        start = max(buffered_start, five_years_ago)
        end = base_end

        df = yf.download(stock_id, start=start, end=end, progress=False)
        
        # 處理 yfinance 多層索引
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        # 允許較短歷史資料（下限可調）
        MIN_REQUIRED_ROWS = 30
        if df.empty or len(df) < MIN_REQUIRED_ROWS:
            return None
        
        return TechProvider._process_indicators(df)

    @staticmethod
    def fetch_data_batch(tickers: List[str], start_date):
        """批量下載多檔股票資料 (優化效能)"""
        today = pd.Timestamp.today().normalize()
        base_end = today + pd.DateOffset(days=1)

        try:
            user_start = pd.to_datetime(start_date).normalize() if start_date is not None else today - pd.DateOffset(years=5)
        except Exception:
            user_start = today - pd.DateOffset(years=5)

        buffered_start = user_start - pd.Timedelta(days=100)
        five_years_ago = today - pd.DateOffset(years=5)
        start = max(buffered_start, five_years_ago)
        end = base_end

        if not tickers:
            return {}
        
        logger.debug("Batch downloading %d stocks...", len(tickers))
        data = yf.download(tickers, start=start, end=end, group_by='ticker', progress=False, threads=True)
        
        result_dfs = {}
        
        # 如果只有一檔，yfinance 回傳的結構不同，需標準化
        if len(tickers) == 1:
            t = tickers[0]
            df = data
            processed = TechProvider._process_indicators(df)
            if processed is not None:
                result_dfs[t] = processed
            return result_dfs

        # 多檔處理
        for t in tickers:
            try:
                df = data[t].dropna(how='all') 
                processed = TechProvider._process_indicators(df)
                if processed is not None:
                    result_dfs[t] = processed
            except Exception:
                continue
                
        return result_dfs

    @staticmethod
    def _process_indicators(df: pd.DataFrame):
        """(內部方法) 為 DataFrame 計算技術指標"""
        if df.empty or len(df) < 30:
            return None
        
        df = df.copy()
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            pass
        
        # --- 均線計算 ---
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA10'] = df['Close'].rolling(window=10).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA60_Slope'] = df['MA60'].diff()
        df['MA60_Rising'] = df['MA60_Slope'].rolling(3).min() > 0 

        # 短線多頭啟動訊號
        df['Break_Price_MA5'] = (
            (df['Close'].shift(1) <= df['MA5'].shift(1)) &
            (df['Close'] > df['MA5'])
        )
        df['MA5_Break_MA10'] = (
            (df['MA5'].shift(1) <= df['MA10'].shift(1)) &
            (df['MA5'] > df['MA10'])
        )
        df['MA5_Up'] = df['MA5'] > df['MA5'].shift(1)
        
        # 成交量
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        df['Vol_Up'] = df['Volume'] > df['Vol_MA5']
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
        df['Vol_MA60'] = df['Volume'].rolling(window=60).mean()

        # 關鍵位置
        df['High_60'] = df['High'].rolling(60).max()
        df['Low_60'] = df['Low'].rolling(60).min()

        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / (loss + 1e-10)  # 避免除零
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD（使用台股常見命名：DIF, DEA）
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema12 - ema26  # 快線
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()  # 慢線
        df['MACD_Hist'] = df['DIF'] - df['DEA']  # 柱狀圖
        
        # 同時保留 MACD/MACD_Signal 命名（向後相容）
        df['MACD'] = df['DIF']
        df['MACD_Signal'] = df['DEA']

        # KDJ 指標 (9, 3, 3)
        low_min = df['Low'].rolling(window=9).min()
        high_max = df['High'].rolling(window=9).max()
        rsv = (df['Close'] - low_min) / (high_max - low_min + 1e-10) * 100  # 避免除零
        df['K'] = rsv.ewm(com=2, adjust=False).mean()  # alpha=1/3 -> com=2
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']

        # --- ATR 計算（供停損緩衝使用）---
        # True Range = max(High - Low, abs(High - prev_Close), abs(Low - prev_Close))
        tr = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Close'].shift()).abs(),
            (df['Low'] - df['Close'].shift()).abs()
        ], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean()
        
        # Swing Low（近10日最低點，供回檔模式停損使用）
        df['Swing_Low_10'] = df['Low'].rolling(10).min()

        return df

class ChipProvider:
    """負責處理籌碼面資料 (FinMind) - 穩健版"""
    
    @staticmethod
    @st.cache_resource
    def get_loader():
        """Resource Cache: 鎖定 DataLoader 實體"""
        if not FINMIND_AVAILABLE:
            return None
        return DataLoader()
    
    @staticmethod
    @st.cache_data(ttl=3600) 
    def fetch_raw_data(stock_id_clean: str, start_date_str: str):
        if not FINMIND_AVAILABLE:
            return None
        try:
            logger.debug("FinMind Fetching %s from %s", stock_id_clean, start_date_str)
            dl = ChipProvider.get_loader()
            if dl is None: return None
            
            # 請求數據
            return dl.taiwan_stock_institutional_investors(
                stock_id=stock_id_clean,
                start_date=start_date_str
            )
        except Exception as e:
            logger.debug("FinMind fetch error: %s", e)
            return None

    @staticmethod
    def get_foreign_data(stock_id: str, start_date) -> Optional[pd.DataFrame]:
        """清洗並計算外資數據 (模糊搜尋版)"""
        if not FINMIND_AVAILABLE:
            return None
        try:
            stock_id_clean = stock_id.split('.')[0]
            # 調整日期：往前推45天以確保有足夠數據計算均線
            adjusted_start = pd.to_datetime(start_date) - pd.Timedelta(days=45)
            start_date_str = adjusted_start.strftime('%Y-%m-%d')
            
            df = ChipProvider.fetch_raw_data(stock_id_clean, start_date_str)
            if df is None or df.empty: 
                logger.debug("FinMind returned empty for %s", stock_id_clean)
                return None
            
            # 欄位名稱檢查 (FinMind 欄位通常是 'name')
            name_col = 'name' if 'name' in df.columns else df.columns[0]
            
            # [關鍵修正] 使用 str.contains 模糊比對，抓取 "外資" 或 "Foreign"
            mask = df[name_col].astype(str).str.contains('Foreign|外資|Foreign_Investor', case=False, na=False)
            df_foreign = df[mask]
            
            if df_foreign.empty:
                logger.debug("No data matched filter '外資|Foreign'. Stock: %s", stock_id_clean)
                return None

            # 處理同日期多筆資料 (groupby sum)
            date_col = 'date'
            if date_col not in df_foreign.columns:
                # 嘗試找日期欄位
                cols = [c for c in df_foreign.columns if 'date' in c.lower()]
                if cols: date_col = cols[0]
                else: return None

            df_foreign = df_foreign.groupby(date_col)[['buy', 'sell']].sum().reset_index()
            
            # 計算買賣超 (張數)
            df_foreign['Net_Buy'] = (df_foreign['buy'] - df_foreign['sell']) / 1000 
            df_foreign[date_col] = pd.to_datetime(df_foreign[date_col])
            df_foreign.set_index(date_col, inplace=True)
            
            # 計算 5日籌碼均線
            df_foreign['Chip_MA5'] = df_foreign['Net_Buy'].rolling(5).mean()
            
            logger.debug("Processed chips for %s, rows: %d", stock_id_clean, len(df_foreign))
            return df_foreign
        except Exception as e:
            logger.debug("ChipProvider Error: %s", e)
            return None

@st.cache_data(ttl=60)
def fetch_latest_prices_batch(codes_tuple: tuple) -> Dict[str, Optional[float]]:
    """一次下載多檔最新收盤價，快取 60 秒。參數需為 tuple 以可 hash。"""
    if not codes_tuple:
        return {}
    codes = list(codes_tuple)
    try:
        df = yf.download(codes, period="1d", progress=False, group_by="ticker", auto_adjust=True, threads=True)
        if df is None or df.empty:
            return {c: None for c in codes}
        result = {}
        if isinstance(df.columns, pd.MultiIndex):
            # group_by='ticker' -> (Ticker, Price_Type)
            for c in codes:
                try:
                    if (c, "Close") in df.columns:
                        result[c] = float(df[(c, "Close")].iloc[-1])
                    else:
                        result[c] = None
                except Exception:
                    result[c] = None
        else:
            # 單檔時可能為一般欄位
            try:
                result[codes[0]] = float(df["Close"].iloc[-1]) if "Close" in df.columns else None
            except Exception:
                result[codes[0]] = None
            for c in codes[1:]:
                result[c] = None
        for c in codes:
            if c not in result:
                result[c] = None
        return result
    except Exception as e:
        logger.debug("fetch_latest_prices_batch error: %s", e)
        return {c: None for c in codes}

# ==========================================
# 4. 核心邏輯層 (Business Logic)
# ==========================================
def analyze_stock(stock_id, start_date, include_chips=False) -> Optional["StockAnalysisResult"]:
    try:
        ticker = yf.Ticker(stock_id)
        try: info = ticker.info
        except: info = {}
        
        user_start = pd.to_datetime(start_date)
        df = TechProvider.fetch_data(stock_id, start_date)
        if df is None: return None

        # 分析與策略一律使用完整資料（最近 5 年），不受分析起始日影響
        df_tech = df.copy()

        # 選擇性抓取籌碼 (單股體檢才抓，避免掃描時太慢)
        df_chips = None
        if include_chips:
            df_chips = ChipProvider.get_foreign_data(stock_id, user_start)

        curr = df_tech.iloc[-1]
        prev = df_tech.iloc[-2]
        score = 0
        passed_reasons = []

        # --- 評分邏輯 ---
        # 1. 估值
        pe = info.get('trailingPE', float('inf'))
        if pe is None: pe = float('inf')
        if pe < 25: score += 1; passed_reasons.append("PE<25")
        
        peg = info.get('pegRatio', float('inf'))
        if peg is not None and peg <= 1.2: score += 1; passed_reasons.append("PEG優")
        
        earnings_growth = info.get('earningsGrowth', None)
        if earnings_growth is not None and earnings_growth > 0.1: 
            score += 1; passed_reasons.append("EPS成長>10%")
        elif info.get('trailingEps', 0) > 0: score += 0.5 

        revenue_growth = info.get('revenueGrowth', 0)
        if revenue_growth > 0.1: score += 1; passed_reasons.append("營收雙位數成長")

        # 2. 趨勢
        if curr['MA20'] > curr['MA60']: score += 1; passed_reasons.append("均線多頭")
        if curr['Close'] > curr['MA60']: score += 1; passed_reasons.append("站上季線")
        if curr['MA60_Rising']: score += 1; passed_reasons.append("季線上彎")

        # 3. 動能
        rsi_golden_cross = (prev['RSI'] < 40) and (curr['RSI'] >= 40)
        if rsi_golden_cross: score += 1; passed_reasons.append("RSI翻揚")
        macd_turning_up = (curr['MACD_Hist'] > 0) and (curr['MACD_Hist'] > prev['MACD_Hist'])
        if macd_turning_up: score += 1; passed_reasons.append("MACD轉強")

        # 4. 價量
        if curr['Close'] > curr['High_60']: score += 1; passed_reasons.append("突破前高")
        vol_ratio = curr['Volume'] / curr['Vol_MA20']
        if vol_ratio >= 1.3: score += 1; passed_reasons.append("爆量")

        final_score = (score / 10) * 100
        
        fundamentals = {
            "PE": pe, "EPS": info.get('trailingEps', 0), 
            "PEG": peg, "Growth": earnings_growth, "Close": curr['Close']
        }

        return StockAnalysisResult(
            stock_id=stock_id,
            score=final_score,
            reasons=passed_reasons,
            tech_df=df_tech,
            fundamentals=fundamentals,
            chips_df=df_chips
        )

    except Exception as e:
        logger.debug("Analyze Error: %s", e)
        return None



def ma5_breakout_ma10_filter(stock_id, start_date, pre_fetched_df=None):
    """
    MA5 突破 MA10 篩選函數
    
    條件：
    1. 股價站上5日線（close > MA5）
    2. 5日線突破10日線（前一日 MA5 <= MA10，當日 MA5 > MA10）
    """
    try:
        ticker = yf.Ticker(stock_id)
        try: 
            info = ticker.info
        except: 
            info = {}
        
        if pre_fetched_df is not None:
            df = pre_fetched_df
        else:
            df = TechProvider.fetch_data(stock_id, start_date)
        
        if df is None or len(df) < 2: 
            return None
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 條件1：股價站上5日線
        close = float(curr['Close'])
        ma5_curr = float(curr.get('MA5', float('nan')))
        ma5_prev = float(prev.get('MA5', float('nan')))
        ma10_curr = float(curr.get('MA10', float('nan')))
        ma10_prev = float(prev.get('MA10', float('nan')))
        
        # 檢查是否有 NaN
        if pd.isna(ma5_curr) or pd.isna(ma5_prev) or pd.isna(ma10_curr) or pd.isna(ma10_prev):
            return None
        
        # 條件1：股價站上5日線
        condition1 = close > ma5_curr
        
        # 條件2：股價站上10日線
        condition2 = close > ma10_curr

        # 條件3：5日線突破10日線（前一日 MA5 <= MA10，當日 MA5 > MA10）
        condition3 = (ma5_prev <= ma10_prev) and (ma5_curr > ma10_curr)
        
        if condition1 and condition2 and condition3:
            # 基本面資訊（僅供參考）
            pe = info.get('trailingPE', float('inf'))
            if pe is None: 
                pe = float('inf')
            
            return {
                "id": stock_id,
                "close": close,
                "ma5": ma5_curr,
                "ma10": ma10_curr,
                "pe": pe,
                "rsi": curr.get('RSI', 0),
                "status": "✅ 符合條件",
            }
        else:
            return None
    except Exception as e:
        logger.debug("ma5_breakout_ma10_filter error for %s: %s", stock_id, e)
        return None

# ==========================================
# 5. 策略轉譯層 (Adapter)
# ==========================================
def strategy_engine(df, stock_id, fundamentals):
    from core.models import ValuationRequest
    pe = fundamentals.get("PE") if fundamentals else None
    eps = fundamentals.get("EPS") if fundamentals else None
    growth = fundamentals.get("Growth") if fundamentals else None
    val_req = ValuationRequest(pe=pe, eps=eps, yoy_growth=growth)
    
    signal = StrategyEngine.advanced_quant_filter(df, val_req)
    return signal.model_dump() if signal else {}

def advanced_quant_filter(stock_id, start_date, pre_fetched_df=None):
    try:
        ticker = yf.Ticker(stock_id)
        info = getattr(ticker, "info", {}) or {}
        
        df = pre_fetched_df if pre_fetched_df is not None else TechProvider.fetch_data(stock_id, start_date)
        if df is None: return None
        curr = df.iloc[-1]
        
        vol_ma20 = curr.get('Vol_MA20', 0)
        if vol_ma20 < 1000000: return None
        
        pe = info.get('trailingPE', float('inf'))
        if pe is None: pe = float('inf')
        eps = info.get('trailingEps', 0)
        if eps is None: eps = 0
        yoy_growth = info.get('earningsGrowth', None)
        
        fundamentals = {"PE": pe, "EPS": eps, "Growth": yoy_growth}
        strat = strategy_engine(df, stock_id, fundamentals)
        
        signal = strat.get("signal", "NoTrade")
        status = "✅ Buy" if signal == "Buy" else "👀 Watch" if signal == "Watch" else "🚪 Exit" if signal == "Exit" else "觀望"
        
        strat.update({
            "id": stock_id,
            "close": curr['Close'],
            "pe": pe,
            "rsi": curr.get('RSI', 0),
            "status": status,
        })
        return strat
    except Exception as e:
        logger.debug("advanced_quant_filter error for %s: %s", stock_id, e)
        return None

# ==========================================
# 6. 視圖層 (View / UI)
# ==========================================
def render_deep_checkup_view(stock_name, stock_id, result: StockAnalysisResult):
    st.markdown(f"## 🏥 {stock_name} ({stock_id}) 深度投資體檢報告")
    
    df = result.tech_df
    fundamentals = result.fundamentals
    df_chips = result.chips_df
    curr = df.iloc[-1]
    prev = df.iloc[-2]

    # 🧠 策略引擎總結區塊（傳入完整參數以支援新功能）
    try:
        engine = strategy_engine(df, stock_id, fundamentals)
    except Exception as e:
        logger.debug("strategy_engine error: %s", e)
        engine = {
            "signal": "NoTrade",
            "market_regime": "UNKNOWN",
            "mode": None,
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": "資料不足或計算失敗",
            "position_level": PositionLevel.NO_POSITION,
            "stop_loss_price": None,
            "atr": None,
            "stop_loss_method": None,
            "risk_pct": None,
            "exit_conditions": [],
            "not_buy_reasons": [],
            "valuation_warning": False,
        }

    # 提取所有欄位
    signal = engine.get("signal", "NoTrade")
    market_regime = engine.get("market_regime", "UNKNOWN")
    mode = engine.get("mode")
    watch = engine.get("watch", False)
    buy = engine.get("buy", False)
    confidence = engine.get("confidence", 0)
    reason = engine.get("reason", "")
    position_level = engine.get("position_level", PositionLevel.NO_POSITION)
    stop_loss_price = engine.get("stop_loss_price")
    atr = engine.get("atr")
    stop_loss_method = engine.get("stop_loss_method")
    risk_pct = engine.get("risk_pct")
    exit_conditions = engine.get("exit_conditions", [])
    not_buy_reasons = engine.get("not_buy_reasons", [])
    valuation_warning = engine.get("valuation_warning", False)

    st.subheader("🧠 策略引擎判斷 (完整交易卡片)")

    # ─────────────────────────────────────────────────────
    # 訊號徽章顏色設定
    # ─────────────────────────────────────────────────────
    if signal == "Buy":
        sig_color = "#00C851"
        sig_bg    = "rgba(0,200,81,0.12)"
        sig_border= "#00C851"
        sig_emoji = "✅"
        sig_label = "BUY  進場訊號"
        sig_desc  = "條件完整，可執行交易"
    elif signal == "Watch":
        sig_color = "#FFB300"
        sig_bg    = "rgba(255,179,0,0.12)"
        sig_border= "#FFB300"
        sig_emoji = "👀"
        sig_label = "WATCH  觀察候補"
        sig_desc  = "結構成立，等待觸發"
    elif signal == "Exit":
        sig_color = "#FF4B4B"
        sig_bg    = "rgba(255,75,75,0.12)"
        sig_border= "#FF4B4B"
        sig_emoji = "🚪"
        sig_label = "EXIT  出場警示"
        sig_desc  = "建議考慮出場或減碼"
    else:
        sig_color = "#000000"
        sig_bg    = "rgba(0,0,0,0.18)"
        sig_border= "#000000"
        sig_emoji = "⏸️"
        sig_label = "NO TRADE  觀望"
        sig_desc  = "市場結構尚未符合條件"

    # 市場狀態文案
    regime_map = {
        "BULL": ("📈", "BULL 多頭市場", "#00C851"),
        "NEUTRAL": ("📊", "NEUTRAL 盤整市場", "#FFB300"),
        "BEAR": ("📉", "BEAR 空頭市場", "#FF4B4B"),
    }
    regime_icon, regime_txt, regime_clr = regime_map.get(
        market_regime, ("❓", "未知", "#000")
    )

    # 模式文案
    mode_display = {"Trend": "Mode B（趨勢追蹤）", "Pullback": "Mode A（回檔買入）", "NoTrade": "N/A"}.get(mode or "", f"Mode {mode or 'N/A'}")

    # 倉位等級中文
    pos_map = {
        "NO_POSITION": ("⬜", "不建議進場", "#000000"),
        "LIGHT": ("🟡", "輕倉", "#FFB300"),
        "MEDIUM": ("🟠", "標準倉", "#FF8C00"),
        "HEAVY": ("🔴", "重倉", "#FF4B4B"),
        "FULL": ("🔥", "滿倉", "#C62828"),
    }
    # 從 Enum 取出 name (e.g. "NO_POSITION")，fallback to str 去掉前缀
    if hasattr(position_level, "name"):
        pos_key = position_level.name  # Python Enum: .name = "NO_POSITION"
    else:
        raw = str(position_level)
        pos_key = raw.split(".")[-1] if "." in raw else raw  # "PositionLevel.NO_POSITION" → "NO_POSITION"
    pos_icon, pos_txt, pos_clr = pos_map.get(pos_key, ("⬜", pos_key, "#9E9E9E"))


    # ─── 主訊號徽章 ───────────────────────────────────────
    entry_price = engine.get("entry_price", float(curr['Close']))
    
    st.markdown(f"""
    <div style="
        background:{sig_bg};
        border:2px solid {sig_border};
        border-radius:16px;
        padding:20px 24px;
        margin-bottom:16px;
        display:flex;
        align-items:center;
        gap:20px;
    ">
        <div style="font-size:3.2rem;line-height:1">{sig_emoji}</div>
        <div style="flex:1">
            <div style="font-size:1.5rem;font-weight:900;color:{sig_color};letter-spacing:1px">{sig_label}</div>
            <div style="font-size:0.9rem;color:#000;margin-top:2px">{sig_desc}</div>
        </div>
        <div style="text-align:right">
            <div style="font-size:2rem;font-weight:900;color:{sig_color}">{confidence}%</div>
            <div style="font-size:0.75rem;color:#000">信心指數</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ─── 市場狀態 + 策略型態 並排 ─────────────────────────
    col_reg, col_mode, col_pos = st.columns(3)
    with col_reg:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:12px 16px;border-left:4px solid {regime_clr}">
            <div style="font-size:0.72rem;color:#000;text-transform:uppercase;letter-spacing:1px">市場狀態</div>
            <div style="font-size:1.05rem;font-weight:700;color:{regime_clr};margin-top:4px">{regime_icon} {regime_txt}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_mode:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:12px 16px;border-left:4px solid #4FC3F7">
            <div style="font-size:0.72rem;color:#000;text-transform:uppercase;letter-spacing:1px">策略型態</div>
            <div style="font-size:1.05rem;font-weight:700;color:#4FC3F7;margin-top:4px">📐 {mode_display}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_pos:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:12px 16px;border-left:4px solid {pos_clr}">
            <div style="font-size:0.72rem;color:#000;text-transform:uppercase;letter-spacing:1px">建議倉位</div>
            <div style="font-size:1.05rem;font-weight:700;color:{pos_clr};margin-top:4px">{pos_icon} {pos_txt}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    # ─── 信心度進度條 ──────────────────────────────────────
    bar_filled = int(confidence / 10)
    bar_html = "".join([
        f'<div style="flex:1;height:10px;border-radius:4px;background:{"#00C851" if i < bar_filled and confidence >= 70 else "#FFB300" if i < bar_filled and confidence >= 40 else "#FF4B4B" if i < bar_filled else "rgba(255,255,255,0.1)"};margin-right:3px;transition:all 0.3s"></div>'
        for i in range(10)
    ])
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
        <div style="font-size:0.8rem;color:#000;width:50px">信心度</div>
        <div style="display:flex;flex:1">{bar_html}</div>
        <div style="font-size:0.85rem;font-weight:700;color:{sig_color};width:36px;text-align:right">{confidence}%</div>
    </div>
    """, unsafe_allow_html=True)

    # ─── Watch / Buy / 估值 狀態指示燈（僅顯示有效的）──────
    active_tags = []
    if watch:
        active_tags.append("<div style='padding:5px 16px;border-radius:20px;font-size:0.82rem;font-weight:700;background:#00C851;color:white'>✅ WATCH</div>")
    if buy:
        active_tags.append("<div style='padding:5px 16px;border-radius:20px;font-size:0.82rem;font-weight:700;background:#00C851;color:white'>✅ BUY</div>")
    if valuation_warning:
        active_tags.append("<div style='padding:5px 16px;border-radius:20px;font-size:0.82rem;font-weight:700;background:rgba(255,179,0,0.2);color:#FFB300'>⚠️ 估值偏高</div>")
    if not watch and not buy:
        active_tags.append("<div style='padding:5px 16px;border-radius:20px;font-size:0.82rem;font-weight:600;background:rgba(60,60,60,0.3);color:#888'>○ 條件未達進場門檻</div>")
    if active_tags:
        st.markdown(f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin:10px 0'>{''.join(active_tags)}</div>", unsafe_allow_html=True)

    # ─── 交易執行卡片（僅 Buy 顯示）─────────────────────────
    if buy or signal == "Buy":
        st.markdown("#### 📋 交易執行卡片")
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.metric("📥 參考進場價", f"${entry_price:.2f}" if entry_price else "N/A")
        with mc2:
            st.metric("🛡️ 停損價", f"${stop_loss_price:.2f}" if stop_loss_price else "N/A",
                      delta=f"-{risk_pct:.1f}%" if risk_pct else None,
                      delta_color="inverse")
        with mc3:
            st.metric("📏 ATR (14)", f"{atr:.2f}" if atr else "N/A")
        with mc4:
            st.metric("⚡ 風險 %", f"{risk_pct:.2f}%" if risk_pct else "N/A")
        if stop_loss_method:
            st.caption(f"🔧 停損方法：{stop_loss_method}")
        st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:16px 0'>", unsafe_allow_html=True)

    # ─── 策略細節與備註 (判斷理由 + 出場 + 不買) ─────────────────
    reasons_list = engine.get("reasons", [])
    if isinstance(reasons_list, list) and reasons_list:
        reason_text = "；".join(str(r) for r in reasons_list if r)
    else:
        reason_text = str(reason) if reason else ""
        
    has_notes = bool(exit_conditions) or (not_buy_reasons and not buy) or bool(reason_text)

    
    if has_notes:
        total_items = (len(exit_conditions) if exit_conditions else 0) + \
                      (len(not_buy_reasons) if not_buy_reasons and not buy else 0)
                      
        expander_label = f"📋 策略備註與細節 ({total_items} 項)"
        with st.expander(expander_label, expanded=False):
            # 1. 核心判斷理由 (原本在外面，現在收進來最上方)
            if reason_text:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03); border-left:3px solid #555; padding:8px 12px; margin-bottom:12px; border-radius:4px">
                    <div style="font-size:0.75rem; color:#888; margin-bottom:4px">💬 核心判斷理由</div>
                    <div style="font-size:0.9rem; color:#000; font-weight:500">{reason_text}</div>
                </div>
                """, unsafe_allow_html=True)

            # 2. 出場與不買理由 (並排或分段)
            if exit_conditions or (not_buy_reasons and not buy):
                col_ex, col_nbr = st.columns(2) if (exit_conditions and (not_buy_reasons and not buy)) else (st.container(), st.container())
                
                with col_ex:
                    if exit_conditions:
                        st.markdown("<div style='font-size:0.78rem;color:#000;font-weight:700;margin-bottom:6px'>🚪 出場條件</div>", unsafe_allow_html=True)

                        for cond in exit_conditions:
                            if any(k in cond for k in ["趨勢破壞", "過熱", "死叉"]):
                                clr, bg, icon = "#FF4B4B", "rgba(255,75,75,0.1)", "🔥"
                            elif any(k in cond for k in ["防守出場", "趨勢結束", "MA20下彎", "跌破季線"]):
                                clr, bg, icon = "#FFB300", "rgba(255,179,0,0.1)", "⚠️"
                            else:
                                clr, bg, icon = "#4FC3F7", "rgba(79,195,247,0.1)", "📉"
                            
                            st.markdown(f"""
                            <div style="display:flex; align-items:center; background:{bg}; border-radius:6px; padding:6px 12px; margin-bottom:4px; border-left:3px solid {clr}">
                                <span style="margin-right:8px">{icon}</span>
                                <span style="font-size:0.85rem; color:#000; font-weight:500">{cond}</span>
                            </div>
                            """, unsafe_allow_html=True)

                with col_nbr:
                    if not_buy_reasons and not buy:
                        st.markdown("<div style='font-size:0.78rem;color:#000;font-weight:700;margin-bottom:6px'>❌ 不買入原因</div>", unsafe_allow_html=True)
                        for r in not_buy_reasons:
                            st.markdown(f"""
                            <div style="font-size:0.84rem; color:#000; padding:4px 0; border-bottom:1px solid rgba(0,0,0,0.05)">
                                • {r}
                            </div>
                            """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:20px'></div>", unsafe_allow_html=True)

    # 1. 估值面
    st.subheader("1️⃣ 估值面診斷 (相對標準)")
    c1, c2 = st.columns(2)
    val_score = 0
    with c1:
        check_item("本益比 P/E", fundamentals['PE'], fundamentals['PE'] < 30, "(< 30 合理)")
        peg_val = fundamentals['PEG'] if fundamentals['PEG'] is not None else float('inf')
        p2 = check_item("成長修正 PEG", peg_val, peg_val <= 1.2, "(標準 ≤ 1.2)")
        if fundamentals['PE'] < 25: val_score +=1
        if p2: val_score +=1
    with c2:
        gw_val = fundamentals['Growth'] if fundamentals['Growth'] is not None else 0
        check_item("EPS 成長率 (YoY)", gw_val * 100, gw_val > 0.1, "% (需 > 10)")
        st.write(f"ℹ️ 最近 EPS: {fundamentals['EPS']:.2f} 元")
        if gw_val > 0: val_score += 1
        if gw_val > 0.15: val_score += 1

    if val_score >= 3: st.success(f"💎 估值評價：優良 ({val_score}/4)")
    elif val_score >= 2: st.warning(f"⚠️ 估值評價：普通 ({val_score}/4)")
    else: st.error(f"💀 估值評價：昂貴或衰退 ({val_score}/4)")
    st.markdown("---")



    # 5. 籌碼面
    if df_chips is not None and not df_chips.empty:
        st.subheader("5️⃣ 外資籌碼動向 (Foreign Investor)")
        
        # 對齊並補值
        aligned_chips = df_chips.reindex(df.index).ffill() 
        if aligned_chips.empty:
             st.warning("⚠️ 籌碼資料日期與 K 線無法對齊")
        else:
            last_chip = aligned_chips.iloc[-1]
            if pd.isna(last_chip['Net_Buy']):
                st.warning("⚠️ 查無外資數據 (盤中可能尚未更新)")
            else:
                c_color = COLOR_UP if last_chip['Net_Buy'] > 0 else COLOR_DOWN
                net_buy_val = last_chip['Net_Buy']
                st.markdown(f"**最新外資買賣超**: <span style='color:{c_color};font-weight:bold;'>{net_buy_val:.0f} 張</span>", unsafe_allow_html=True)
                
                recent_5_days = aligned_chips['Net_Buy'].tail(5).sum()
                chip_status = "外資連買" if recent_5_days > 0 else "外資調節"
                st.info(f"💡 近5日外資累計: {recent_5_days:.0f} 張 ({chip_status})")
                # 外資轉向的文字提示也可以保留短期的，不寫入 session table
                switch = detect_chip_switch(aligned_chips)
                if switch is not None:
                    kind, prev_val, last_val = switch
                    if "賣轉買" in kind:
                        st.success(f"🚨 外資轉向：由賣轉買 — 前: {prev_val:.0f} 張 → 現: {last_val:.0f} 張")
                    elif "買轉賣" in kind:
                        st.warning(f"⚠️ 外資轉向：由買轉賣 — 前: {prev_val:.0f} 張 → 現: {last_val:.0f} 張")
    else:
        if not FINMIND_AVAILABLE:
            st.warning("⚠️ FinMind 套件未安裝，無法顯示外資數據。\n安裝指令: `pip install FinMind`")
        else:
            st.warning("⚠️ 查無外資數據 (FinMind 連線逾時或該股票無外資資料)")
    
    st.markdown("---")



    # ========================================================
    # 📊 圖表區
    # ========================================================
    # 根據側邊欄「分析起始日」決定線圖顯示區間（僅影響圖表，不影響指標與策略判斷）
    start_cut = st.session_state.get('analysis_start_date', None)
    used_fallback_full = False
    if start_cut is not None:
        try:
            start_cut = pd.to_datetime(start_cut)
            df_plot = df[df.index >= start_cut].copy()
            if df_plot.empty:
                # 若選到未來或資料不足，改回顯示完整區間，並給使用者提醒
                df_plot = df
                used_fallback_full = True
        except Exception:
            df_plot = df
            used_fallback_full = True
    else:
        df_plot = df

    if used_fallback_full:
        st.info("📅 目前選擇的分析起始日超出可用資料範圍，線圖已自動顯示完整期間。")

    # 📊 圖表區 (5列布局：K線、成交量、KDJ、外資買賣超、MACD)
    # ========================================================
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        row_heights=[0.32, 0.15, 0.18, 0.18, 0.17],
        vertical_spacing=0.05,
        subplot_titles=("K線與關鍵位", "成交量", "KDJ 指標", "外資買賣超(張)", "MACD 指標"),
        specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}]]
    )
    
    # --- Row 1: K線 ---
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], 
        name='K線',
        increasing_line_color=COLOR_UP,
        increasing_fillcolor=COLOR_UP,
        decreasing_line_color=COLOR_DOWN,
        decreasing_fillcolor=COLOR_DOWN
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA5'], line=dict(color='purple', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA10'], line=dict(color='#00BCD4', width=1), name='MA10'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['High_60'], line=dict(color='gray', dash='dash'), name='60日高 (壓力)'), row=1, col=1)

    # --- 停損線標註 ---
    if stop_loss_price and stop_loss_price > 0:
        fig.add_trace(go.Scatter(
            x=df_plot.index, 
            y=[stop_loss_price] * len(df_plot), 
            line=dict(color='red', width=2, dash='dot'), 
            name=f'停損參考 {stop_loss_price:.2f}'
        ), row=1, col=1)
    # --- Row 2: 成交量 (顏色跟隨當日漲跌，單位改為「張」) ---
    price_change = df_plot['Close'] - df_plot['Close'].shift(1)
    colors_vol = [COLOR_UP if c >= 0 else COLOR_DOWN for c in price_change]
    volume_in_lots = df_plot['Volume'] / 1000  # 股數轉張數
    fig.add_trace(go.Bar(x=df_plot.index, y=volume_in_lots, marker_color=colors_vol, name='成交量(張)', legend='legend2'), row=2, col=1)

    # --- Row 3: KDJ ---
    if 'K' in df_plot.columns and 'D' in df_plot.columns:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['K'], line=dict(color='#FF8C00', width=1.2), name='K值', legend='legend3'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['D'], line=dict(color='#00BCD4', width=1.2), name='D值', legend='legend3'), row=3, col=1)
        if 'J' in df_plot.columns:
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['J'], line=dict(color='#E040FB', width=1, dash='dot'), name='J值', legend='legend3'), row=3, col=1)
        # 超買(80)、超賣(20) 參考線
        fig.add_hline(y=80, line=dict(color='red', width=0.8, dash='dash'), row=3, col=1)
        fig.add_hline(y=20, line=dict(color='green', width=0.8, dash='dash'), row=3, col=1)

    # --- Row 4: 外資買賣超 ---
    if df_chips is not None and not df_chips.empty:
        aligned_chips = df_chips.reindex(df_plot.index).ffill()
        colors_chip = []
        for v in aligned_chips['Net_Buy']:
            if pd.isna(v):
                colors_chip.append('gray')
            elif v > 0:
                colors_chip.append(COLOR_UP)
            else:
                colors_chip.append(COLOR_DOWN)

        fig.add_trace(
            go.Bar(
                x=aligned_chips.index,
                y=aligned_chips['Net_Buy'],
                marker_color=colors_chip,
                name='外資買賣超',
                legend='legend4'
            ),
            row=4,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=aligned_chips.index,
                y=aligned_chips['Chip_MA5'],
                line=dict(color='#ffd700', width=1.5),
                name='外資5MA',
                legend='legend4'
            ),
            row=4,
            col=1,
        )

    # --- Row 5: MACD ---
    colors_macd = [COLOR_UP if v >= 0 else COLOR_DOWN for v in df_plot['MACD_Hist']]
    fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['MACD_Hist'], marker_color=colors_macd, name='MACD柱狀', legend='legend5'), row=5, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['DIF'], line=dict(color='#2962FF', width=1), name='DIF (快)', legend='legend5'), row=5, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['DEA'], line=dict(color='#FF6D00', width=1), name='DEA (慢)', legend='legend5'), row=5, col=1)

    fig.update_layout(
        height=1250,
        xaxis_rangeslider_visible=False,
        title_text=f"{stock_id} 綜合分析圖",
        hovermode='x unified',
        legend=dict(y=1.0, yanchor="top", x=1.02, xanchor="left"),
        legend2=dict(y=0.68, yanchor="top", x=1.02, xanchor="left"),
        legend3=dict(y=0.53, yanchor="top", x=1.02, xanchor="left"),
        legend4=dict(y=0.35, yanchor="top", x=1.02, xanchor="left"),
        legend5=dict(y=0.17, yanchor="top", x=1.02, xanchor="left"),
    )

    # 設定 Y 軸標題
    fig.update_yaxes(title_text="成交量(張)", row=2, col=1)
    fig.update_yaxes(title_text="KDJ", row=3, col=1)
    fig.update_yaxes(title_text="外資買賣超", row=4, col=1)
    fig.update_yaxes(title_text="MACD", row=5, col=1)

    st.plotly_chart(fig, use_container_width=True)

# 輔助功能
def check_item(label, value, condition, suffix=""):
    icon = "✅" if condition else "❌"
    color = "green" if condition else "red"
    val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
    st.markdown(f":{color}[{icon} **{label}**]：{val_str} {suffix}")
    return condition

def detect_chip_switch(aligned_chips: pd.DataFrame):
    """檢測外資買賣超由賣轉買或由買轉賣。
    主要以 `Net_Buy` 的最後兩個非 NA 值判斷；若不足則以 `Chip_MA5` 判斷。
    回傳 (kind, prev_val, last_val) 或 None。
    """
    try:
        if aligned_chips is None or aligned_chips.empty:
            return None

        s = aligned_chips['Net_Buy'].dropna()
        if len(s) >= 2:
            prev_val = s.iloc[-2]
            last_val = s.iloc[-1]
            if prev_val <= 0 and last_val > 0:
                return ("賣轉買", prev_val, last_val)
            if prev_val >= 0 and last_val < 0:
                return ("買轉賣", prev_val, last_val)

        # 若 Net_Buy 不足以判斷，改用 Chip_MA5 的交叉
        ma = aligned_chips['Chip_MA5'].dropna()
        if len(ma) >= 2:
            prev_ma = ma.iloc[-2]
            last_ma = ma.iloc[-1]
            if prev_ma <= 0 and last_ma > 0:
                return ("賣轉買(MA)", prev_ma, last_ma)
            if prev_ma >= 0 and last_ma < 0:
                return ("買轉賣(MA)", prev_ma, last_ma)

        return None
    except Exception:
        return None

def record_chip_event(stock_id: str, kind: str, prev_val: float, last_val: float, date):
    """將外資轉向事件存入 `st.session_state['chip_switch_history']`（session 內暫存）。"""
    try:
        if 'chip_switch_history' not in st.session_state:
            st.session_state['chip_switch_history'] = []

        event = {
            'stock_id': stock_id,
            'type': kind,
            'prev': float(prev_val),
            'last': float(last_val),
            'date': pd.to_datetime(date).strftime('%Y-%m-%d')
        }

        # 避免重複記錄（若最後一筆相同則略過）
        hist = st.session_state['chip_switch_history']
        if not hist or not (hist[-1]['stock_id'] == event['stock_id'] and hist[-1]['type'] == event['type'] and hist[-1]['date'] == event['date']):
            hist.append(event)
            # 限制歷史長度
            if len(hist) > 50:
                st.session_state['chip_switch_history'] = hist[-50:]
            else:
                st.session_state['chip_switch_history'] = hist

        # 也記錄最近一次事件供快速顯示
        st.session_state[f'last_chip_switch_{stock_id}'] = event
    except Exception:
        pass

def render_chip_history_table(stock_id: str):
    """在 UI 中顯示最近的外資轉向紀錄（僅 session 內）。"""
    st.subheader("📜 外資轉向紀錄 (Session)")
    if 'chip_switch_history' not in st.session_state or not st.session_state['chip_switch_history']:
        st.info("目前無外資轉向歷史紀錄。")
        return
    dfh = pd.DataFrame(st.session_state['chip_switch_history'])
    # 顯示該股票的紀錄（若無則顯示全域最近 5 筆）
    df_stock = dfh[dfh['stock_id'] == stock_id]
    if df_stock.empty:
        df_show = dfh.tail(5).iloc[::-1]
    else:
        df_show = df_stock.iloc[::-1]

    # 為每一筆事件建立中文摘要
    def _build_summary(row):
        kind = str(row.get('kind', '') or row.get('type', '') or '')
        prev_v = float(row.get('prev', 0))
        last_v = float(row.get('last', 0))
        date_s = str(row.get('date', ''))
        if kind in ("sell_to_buy", "賣轉買"):
            direction = "由賣轉買"
        elif kind in ("buy_to_sell", "買轉賣"):
            direction = "由買轉賣"
        else:
            direction = "轉向"
        return f"{date_s}：外資{direction}，{prev_v:.0f} → {last_v:.0f} 張"

    df_show = df_show.copy()
    df_show['summary'] = df_show.apply(_build_summary, axis=1)

    # 只顯示關鍵欄位與摘要（若缺欄位則盡量容錯）
    expected_cols = ['stock_id', 'kind', 'prev', 'last', 'date', 'summary']
    available_cols = [c for c in expected_cols if c in df_show.columns]
    if not available_cols:
        st.info("外資轉向紀錄格式異常，暫時無法顯示列表。")
        return
    df_render = df_show[available_cols].reset_index(drop=True)
    
    # 將表頭改為中文
    df_render.columns = [
        {'stock_id':'股票代號', 'kind':'轉向類型', 'prev':'前日買賣超', 'last':'今日買賣超', 'date':'日期', 'summary':'摘要說明'}.get(c, c) 
        for c in df_render.columns
    ]

    st.dataframe(apply_table_style(df_render).hide(axis='index'), use_container_width=True)

def go_back_logic():
    st.session_state['current_page'] = st.session_state['previous_page']
    st.session_state['target_stock'] = None
    st.session_state['dataframe_key'] += 1

# ==========================================
# 6. 主程式 - 側邊欄與頁面導航
# ==========================================
st.sidebar.title("🎮 功能選單")
if 'current_page' not in st.session_state: st.session_state['current_page'] = "🏆 台灣50 (排除金融)"
if 'previous_page' not in st.session_state: st.session_state['previous_page'] = "🏆 台灣50 (排除金融)"
if 'target_stock' not in st.session_state: st.session_state['target_stock'] = None
if 'dataframe_key' not in st.session_state: st.session_state['dataframe_key'] = 0

if 'scan_results_tw50' not in st.session_state: st.session_state['scan_results_tw50'] = None
if 'scan_results_sector_buy' not in st.session_state: st.session_state['scan_results_sector_buy'] = None
if 'scan_results_sector_warn' not in st.session_state: st.session_state['scan_results_sector_warn'] = None
if 'scan_results_ma5_breakout' not in st.session_state: st.session_state['scan_results_ma5_breakout'] = None
if 'scan_results_ma5_breakout_ma10' not in st.session_state: st.session_state['scan_results_ma5_breakout_ma10'] = None
if 'scan_results_ai_concept' not in st.session_state: st.session_state['scan_results_ai_concept'] = None

# 從文件加載觀察清單
if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = load_watchlist()

page_options = ["🌊 市場資金流向 (法人單日板塊)", "🏆 台灣50 (排除金融)", "🤖 AI概念股", "🚀 全自動量化選股 (動態類股版)", "📈 MA5突破MA10掃描", "📦 我持有的股票診斷", "⭐ 觀察清單", "🔍 單一個股體檢"]

def update_nav(): st.session_state['current_page'] = st.session_state['nav_radio']
try: nav_index = page_options.index(st.session_state['current_page'])
except ValueError: nav_index = 0

st.sidebar.radio("請選擇模式", page_options, index=nav_index, key="nav_radio", on_change=update_nav)


def clear_temp_data():
    """清除會受條件改變影響的暫存結果，避免 UI 顯示舊資料。"""
    for k in [
        'scan_results_tw50',
        'scan_results_ai_concept',
        'scan_results_sector_buy',
        'scan_results_sector_warn',
        'scan_results_ma5_breakout',
        'holdings_analysis',
        'analysis_cache',
    ]:
        st.session_state.pop(k, None)


# 預設為一個月前
default_start_date = pd.Timestamp.today() - pd.DateOffset(months=1)
start_date = st.sidebar.date_input(
    "分析起始日", 
    default_start_date,
    help="主要影響趨勢圖的顯示範圍，不影響技術指標與策略判斷的計算"
)

# 偵測分析起始日是否變更，若有變更則清空暫存資料
prev_start = st.session_state.get('prev_analysis_start_date')
if prev_start is None or pd.to_datetime(prev_start) != pd.to_datetime(start_date):
    clear_temp_data()
    st.session_state['prev_analysis_start_date'] = pd.to_datetime(start_date)

st.session_state['analysis_start_date'] = pd.to_datetime(start_date)
mode = st.session_state['current_page']

# ----------------- 頁面: 市場資金流向 -----------------
if mode == "🌊 市場資金流向 (法人單日板塊)":
    st.header("🌊 市場資金流向 (法人單日板塊)")
    st.markdown("追蹤最近一個交易日，三大法人（外資、投信、自營商）淨流入/流出的熱點族群。")
    
    if st.button("📊 載入資金流向資料", type="primary"):
        with st.spinner("正在取得 FinMind 法人買賣超資料..."):
            reports = FundFlowService.get_sector_fund_flow_report()
            latest_date = FundFlowService.get_latest_date_available()
            
            if not reports:
                st.warning(f"無法取得 {latest_date} 的法人買賣超資料，可能是 API 限制或當日無資料。")
            else:
                st.success(f"資料日期：{latest_date} (更新成功)")
                
                # 準備繪圖資料：取前 15 大淨流入與前 5 大淨流出 (或全部)
                df_plot = pd.DataFrame([
                    {"板塊": r.sector_name, "淨流入(元)": r.total_net_flow}
                    for r in reports
                ])
                
                # 著色：大於 0 為紅，小於 0 為綠 (台股習慣)
                df_plot['顏色'] = df_plot['淨流入(元)'].apply(lambda x: COLOR_UP if x > 0 else COLOR_DOWN)
                
                fig = go.Figure(go.Bar(
                    x=df_plot['淨流入(元)'],
                    y=df_plot['板塊'],
                    orientation='h',
                    marker_color=df_plot['顏色'],
                    text=df_plot['淨流入(元)'].apply(lambda x: f"{x:,.0f}"),
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title=f"三大法人單日淨買賣超 (依板塊) - {latest_date}",
                    xaxis_title="淨買賣超金額 (單位: 元)",
                    yaxis_title="產業板塊",
                    yaxis={'categoryorder':'total ascending'}, # 讓最多的在最上面
                    height=max(600, len(df_plot) * 30),
                    template="plotly_white"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("### 🏆 各板塊領頭羊 (淨買超榜)")
                st.markdown("👇 點開板塊卡片可查看該板塊前三大買超個股明細")
                
                # 過濾出淨買超大於0的板塊
                positive_sectors = [r for r in reports if r.total_net_flow > 0]
                
                if not positive_sectors:
                    st.info("今日無顯著的法人淨買超板塊。")
                else:
                    # 分為2個欄位展示卡片（更寬廣的閱讀體驗）
                    cols = st.columns(2)
                    
                    for i, r in enumerate(positive_sectors[:6]): # 顯示前6名
                        with cols[i % 2]:
                            # 使用 container 包裝卡片
                            with st.container(border=True):
                                # 利用 metric 展示總流入，更有數字感
                                st.metric(label=f"🟢 {r.sector_name}", value=f"{r.total_net_flow:,.0f} 仟元")
                                
                                # 使用 expander 收納個股明細，讓預設畫面更乾淨
                                with st.expander("📝 檢視成分股明細", expanded=(i < 2)): # 預設展開前2名的明細
                                    top_3 = r.details[:3]
                                    if top_3:
                                        # 將 top3 轉換為 DataFrame 呈現，比 bullet points 更整齊
                                        df_details = pd.DataFrame([
                                            {"股票名稱": d.name, "代號": d.code, "買超張數": d.net_buy_sell}
                                            for d in top_3 if d.net_buy_sell > 0
                                        ])
                                        if not df_details.empty:
                                            # 套用 dataframe 隱藏 index 並調整欄寬
                                            st.dataframe(
                                                df_details,
                                                hide_index=True,
                                                use_container_width=True,
                                                column_config={
                                                    "股票名稱": st.column_config.TextColumn("股票名稱"),
                                                    "代號": st.column_config.TextColumn("代號"),
                                                    "買超張數": st.column_config.NumberColumn(
                                                        "買超張數",
                                                        format="%d",
                                                    )
                                                }
                                            )
                                    else:
                                        st.write("無符合條件之個股。")


# ----------------- 頁面 A -----------------
if mode == "🏆 台灣50 (排除金融)":
    st.header("🏆 台灣50 掃描雷達")
    st.info("👇 點擊表格任一行，可進入深度體檢。")
    if st.button("🚀 啟動掃描", type="primary"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        # 使用「台灣50 (排除金融)」真實股票池
        target_list = TAIWAN50_EX_FIN_TICKERS
        
        for i, stock_id in enumerate(target_list):
            stock_name = STOCK_DB.get(stock_id, {}).get("name", stock_id)
            status_text.text(f"掃描中: {stock_name} ...")
            # 掃描模式：不抓籌碼 (include_chips=False)
            res_obj = analyze_stock(stock_id, start_date, include_chips=False)
            if res_obj:
                results.append({
                    "代號": stock_id, "名稱": stock_name, "分數": int(res_obj.score),
                    "收盤價": res_obj.fundamentals['Close'], "通過項目": res_obj.status_summary
                })
            progress_bar.progress((i + 1) / len(target_list))
        progress_bar.empty()
        status_text.empty()
        if results:
            st.session_state['scan_results_tw50'] = pd.DataFrame(results).sort_values(by="分數", ascending=False)
            st.rerun()

    tw50_results = st.session_state.get('scan_results_tw50')
    if tw50_results is not None:
        df_display = tw50_results
        event = st.dataframe(apply_table_style(df_display).hide(axis='index'), on_select="rerun", selection_mode="single-row",
                             use_container_width=True, height=500,
                             key=f"tw50_df_{st.session_state['dataframe_key']}")
        if len(event.selection.rows) > 0:
            idx = event.selection.rows[0]
            st.session_state['target_stock'] = df_display.iloc[idx]['代號']
            st.session_state['previous_page'] = "🏆 台灣50 (排除金融)" 
            st.session_state['current_page'] = "🔍 單一個股體檢"
            st.rerun()

# ----------------- 頁面 A2：AI概念股 -----------------
elif mode == "🤖 AI概念股":
    st.header("🤖 AI 概念股掃描雷達")
    st.info("👇 點擊表格任一行，可進入深度體檢。涵蓋 AI 伺服器、散熱、CoWoS、ASIC 等核心 AI 供應鏈。")
    if st.button("🚀 啟動掃描", type="primary", key="ai_concept_scan"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        target_list = AI_CONCEPT_TICKERS
        
        for i, stock_id in enumerate(target_list):
            # 動態取得股票名稱（優先 STOCK_DB → FinMind → yfinance）
            stock_name = get_stock_display_name(stock_id)
            status_text.text(f"掃描中: {stock_name} ...")
            # 掃描模式：不抓籌碼 (include_chips=False)
            res_obj = analyze_stock(stock_id, start_date, include_chips=False)
            if res_obj:
                # 短線買點偵測：價格突破 5 日線 + MA5 上穿 MA10
                df = res_obj.tech_df
                buy_signal = "❌"
                if df is not None and len(df) >= 2:
                    latest = df.iloc[-1]
                    # 檢查是否有 Break_Price_MA5 和 MA5_Break_MA10 欄位
                    if 'Break_Price_MA5' in df.columns and 'MA5_Break_MA10' in df.columns:
                        # 檢查最近 3 天內是否有觸發買點訊號
                        recent_days = df.tail(3)
                        has_price_break = recent_days['Break_Price_MA5'].any()
                        has_ma_cross = recent_days['MA5_Break_MA10'].any()
                        if has_price_break and has_ma_cross:
                            buy_signal = "🔥 買點"
                        elif has_price_break or has_ma_cross:
                            buy_signal = "⚡ 觀察"
                
                results.append({
                    "代號": stock_id, "名稱": stock_name, "分數": int(res_obj.score),
                    "短線買點": buy_signal,
                    "收盤價": res_obj.fundamentals['Close'], "通過項目": res_obj.status_summary
                })
            progress_bar.progress((i + 1) / len(target_list))
        progress_bar.empty()
        status_text.empty()
        if results:
            # 優先顯示有買點的股票
            df_results = pd.DataFrame(results)
            df_results['_sort_key'] = df_results['短線買點'].map({'🔥 買點': 0, '⚡ 觀察': 1, '❌': 2})
            df_results = df_results.sort_values(by=['_sort_key', '分數'], ascending=[True, False]).drop(columns=['_sort_key'])
            st.session_state['scan_results_ai_concept'] = df_results
            st.rerun()

    ai_results = st.session_state.get('scan_results_ai_concept')
    if ai_results is not None:
        df_display = ai_results
        event = st.dataframe(apply_table_style(df_display).hide(axis='index'), on_select="rerun", selection_mode="single-row",
                             use_container_width=True, height=500,
                             key=f"ai_concept_df_{st.session_state['dataframe_key']}")
        if len(event.selection.rows) > 0:
            idx = event.selection.rows[0]
            st.session_state['target_stock'] = df_display.iloc[idx]['代號']
            st.session_state['previous_page'] = "🤖 AI概念股" 
            st.session_state['current_page'] = "🔍 單一個股體檢"
            st.rerun()

# ----------------- 頁面 B -----------------
elif mode == "🚀 全自動量化選股 (動態類股版)":
    st.header("🚀 全自動量化選股 (動態類股版)")
    st.info("💡 點擊下方類股按鈕，將自動抓取最新成分股並進行批次掃描。")
    
    target_stocks = []
    scan_triggered = False
    batch_mode = False
    stock_info_map = {} # 存放動態抓取的 ID->Name 對照表
    
    all_sectors = SectorProvider.get_sectors()
        
    # 定義需要特殊標示的電子科技類股（橘色底）
    TECH_SECTORS = ["光電業", "半導體業", "電子工業", "電腦及週邊設備業"]
    
    # 建立類股按鈕網格
    if not all_sectors:
        st.error("無法取得類股資料，請檢查 FinMind 連線。")
    else:
        # 橘色按鈕樣式 CSS
        st.markdown("""
        <style>
        .orange-btn > button {
            background-color: #FF9800 !important;
            color: white !important;
            border: none !important;
        }
        .orange-btn > button:hover {
            background-color: #F57C00 !important;
            color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # ===== 電子科技綜合掃描按鈕 =====
        st.markdown("#### 🔥 快速掃描")
        if st.button("⚡ 電子科技綜合掃描（光電/半導體/電子/電腦週邊）", type="primary", use_container_width=True, key="tech_combo_scan"):
            with st.spinner("正在抓取【電子科技綜合】成分股..."):
                combined_stocks = {}
                for sec in TECH_SECTORS:
                    sec_info = SectorProvider.get_sector_stocks_info(sec)
                    combined_stocks.update(sec_info)
                
                stock_info_map = combined_stocks
                target_stocks = list(stock_info_map.keys())
                
                st.session_state['last_scanned_sector'] = "電子科技綜合"
                if target_stocks:
                    st.success(f"已取得 {len(target_stocks)} 檔成分股（來自 {len(TECH_SECTORS)} 個類股）")
                    scan_triggered = True
                    batch_mode = True
                else:
                    st.warning("無法取得成分股，請檢查網路連線。")
            
        st.markdown("#### 📂 單一類股掃描")
        # 每行 6 個按鈕
        cols = st.columns(6)
        for i, sec in enumerate(all_sectors):
            # 判斷是否為電子科技類股，若是則套用橘色樣式
            is_tech = sec in TECH_SECTORS
            col = cols[i % 6]
            
            if is_tech:
                # 使用 container 包裝以套用 CSS class
                with col:
                    st.markdown('<div class="orange-btn">', unsafe_allow_html=True)
                    clicked = st.button(f"🔶 {sec}", use_container_width=True, key=f"sector_{sec}")
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                clicked = col.button(sec, use_container_width=True, key=f"sector_{sec}")
            
            if clicked:
                with st.spinner(f"正在抓取【{sec}】成分股..."):
                    # 改用詳細資訊 (含名稱)
                    stock_info_map = SectorProvider.get_sector_stocks_info(sec)
                    target_stocks = list(stock_info_map.keys())
                    
                    st.session_state['last_scanned_sector'] = sec
                    if target_stocks:
                        st.success(f"已取得 {len(target_stocks)} 檔成分股")
                        scan_triggered = True
                        batch_mode = True # 啟用批次優化
                    else:
                        st.warning("該類股無成分股或抓取失敗。")

    # 執行掃描邏輯
    if scan_triggered and target_stocks:
        buy_list = []
        watch_list = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 決定資料獲取方式
        fetched_data_map = {}
        if batch_mode:
            status_text.text("🚀 正在批次下載技術資料 (加速中)...")
            fetched_data_map = TechProvider.fetch_data_batch(target_stocks, start_date)
        
        total_stocks = len(target_stocks)
        for i, stock_id in enumerate(target_stocks):
            # 優先從動態抓取的 map 找名稱，找不到則回退到 STOCK_DB (Manual)
            stock_name = stock_id
            if stock_info_map and stock_id in stock_info_map:
                stock_name = stock_info_map[stock_id]
            else:
                stock_name = STOCK_DB.get(stock_id, {}).get("name", stock_id) 
            
            status_text.text(f"分析中 ({i+1}/{total_stocks}): {stock_id} ...")
            
            # 使用批次抓好的資料 (若有)
            pre_df = fetched_data_map.get(stock_id) if batch_mode else None
            
            # 傳入 pre_fetched_df（唯一決策來源：strategy_engine）
            res = advanced_quant_filter(stock_id, start_date, pre_fetched_df=pre_df)
            
            if res:
                res['name'] = stock_name
                # 根據 strategy_engine 的 watch / buy 分離清單
                if res.get("buy"):
                    buy_list.append(res)
                elif res.get("watch"):
                    watch_list.append(res)
            progress_bar.progress((i + 1) / total_stocks)
        
        progress_bar.empty()
        status_text.empty()
        
        # 儲存結果：分成 Watch / Buy 兩張清單
        if buy_list:
            df_buy = pd.DataFrame(buy_list)[['id', 'name', 'status', 'reasons', 'close', 'mode', 'confidence']]
            df_buy.columns = ['代號', '名稱', '狀態', '理由', '收盤價', 'Mode', '信心度']
            st.session_state['scan_results_sector_buy'] = df_buy
        else:
            st.session_state['scan_results_sector_buy'] = pd.DataFrame()
        
        if watch_list:
            df_watch = pd.DataFrame(watch_list)[['id', 'name', 'status', 'reasons', 'close', 'mode', 'confidence']]
            df_watch.columns = ['代號', '名稱', '狀態', '理由', '收盤價', 'Mode', '信心度']
            st.session_state['scan_results_sector_warn'] = df_watch
        else:
            st.session_state['scan_results_sector_warn'] = pd.DataFrame()
        
        # 不使用 rerun 以免重置按鈕狀態，直接顯示結果
        # st.rerun() 


    buy_results = st.session_state.get('scan_results_sector_buy')
    buy_count = 0
    if buy_results is not None:
        buy_count = len(buy_results)
    st.subheader(f"✅ Buy 清單 ({buy_count})")
    st.caption("條件完整、可執行交易的標的")
    if buy_results is not None and not buy_results.empty:
        df_buy_show = buy_results
        event_buy = st.dataframe(apply_table_style(df_buy_show).hide(axis='index'), on_select="rerun", selection_mode="single-row",
                                 use_container_width=True,
                                 key=f"sector_buy_{st.session_state['dataframe_key']}")
        if len(event_buy.selection.rows) > 0:
            idx = event_buy.selection.rows[0]
            code_sel = df_buy_show.iloc[idx]['代號']
            name_sel = df_buy_show.iloc[idx]['名稱']
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔍 檢視個股體檢", key="buy_to_detail"):
                    st.session_state['target_stock'] = code_sel
                    st.session_state['previous_page'] = "🚀 全自動量化選股 (動態類股版)"
                    st.session_state['current_page'] = "🔍 單一個股體檢"
                    st.rerun()
            with col_b:
                if st.button("⭐ 加入觀察清單", key="buy_to_watch"):
                    add_to_watchlist(code_sel, name_sel)
                    st.success(f"已加入觀察清單：{code_sel} {name_sel}")
    else: 
        st.write("尚無資料 (請執行掃描)")

    st.markdown("---")
    watch_results = st.session_state.get('scan_results_sector_warn')
    watch_count = 0
    if watch_results is not None:
        watch_count = len(watch_results)
    st.subheader(f"👀 Watch 清單 ({watch_count})")
    st.caption("值得盯，但尚未觸發買點的標的")
    if watch_results is not None and not watch_results.empty:
        df_watch_show = watch_results
        event_watch = st.dataframe(apply_table_style(df_watch_show).hide(axis='index'), on_select="rerun", selection_mode="single-row",
                                  use_container_width=True,
                                  key=f"sector_watch_{st.session_state['dataframe_key']}")
        if len(event_watch.selection.rows) > 0:
            idx = event_watch.selection.rows[0]
            code_sel = df_watch_show.iloc[idx]['代號']
            name_sel = df_watch_show.iloc[idx]['名稱']
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔍 檢視個股體檢", key="watch_to_detail"):
                    st.session_state['target_stock'] = code_sel
                    st.session_state['previous_page'] = "🚀 全自動量化選股 (動態類股版)"
                    st.session_state['current_page'] = "🔍 單一個股體檢"
                    st.rerun()
            with col_b:
                if st.button("⭐ 加入觀察清單", key="watch_to_watchlist"):
                    add_to_watchlist(code_sel, name_sel)
                    st.success(f"已加入觀察清單：{code_sel} {name_sel}")
    else: 
        st.write("尚無資料")

# ----------------- 頁面 C -----------------
elif mode == "📈 MA5突破MA10掃描":
    st.header("📈 MA5 突破 MA10 掃描")
    st.info("👇 掃描符合以下條件的股票：\n1. 股價站上5日線（close > MA5）\n2. 股價站上10日線（close > MA10）\n3. 5日線突破10日線（前一日 MA5 <= MA10，當日 MA5 > MA10）")
    
    st.info("💡 點擊下方類股按鈕，將自動抓取最新成分股並進行批次掃描。")
    
    target_stocks = []
    scan_triggered = False
    batch_mode = False
    stock_info_map = {}
    
    all_sectors = SectorProvider.get_sectors()
    
    # 建立類股按鈕網格
    if not all_sectors:
        st.error("無法取得類股資料，請檢查 FinMind 連線。")
    else:
        # 每行 6 個按鈕
        cols = st.columns(6)
        for i, sec in enumerate(all_sectors):
            if cols[i % 6].button(sec, use_container_width=True, key=f"ma5_breakout_{sec}"):
                with st.spinner(f"正在抓取【{sec}】成分股..."):
                    stock_info_map = SectorProvider.get_sector_stocks_info(sec)
                    target_stocks = list(stock_info_map.keys())
                    
                    if target_stocks:
                        st.success(f"已取得 {len(target_stocks)} 檔成分股")
                        scan_triggered = True
                        batch_mode = True
                    else:
                        st.warning("該類股無成分股或抓取失敗。")
    
    # 執行掃描邏輯
    if scan_triggered and target_stocks:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 決定資料獲取方式
        fetched_data_map = {}
        if batch_mode:
            status_text.text("🚀 正在批次下載技術資料 (加速中)...")
            fetched_data_map = TechProvider.fetch_data_batch(target_stocks, start_date)
        
        total_stocks = len(target_stocks)
        for i, stock_id in enumerate(target_stocks):
            # 優先從動態抓取的 map 找名稱，找不到則回退到 STOCK_DB (Manual)
            stock_name = stock_id
            if stock_info_map and stock_id in stock_info_map:
                stock_name = stock_info_map[stock_id]
            else:
                stock_name = STOCK_DB.get(stock_id, {}).get("name", stock_id)
            
            status_text.text(f"掃描中 ({i+1}/{total_stocks}): {stock_name} ({stock_id}) ...")
            
            # 使用批次抓好的資料 (若有)
            pre_df = fetched_data_map.get(stock_id) if batch_mode else None
            
            # 使用 MA5 突破 MA10 篩選函數
            res = ma5_breakout_ma10_filter(stock_id, start_date, pre_fetched_df=pre_df)
            
            if res:
                res['name'] = stock_name
                results.append(res)
            
            progress_bar.progress((i + 1) / total_stocks)
        
        progress_bar.empty()
        status_text.empty()
        
        # 儲存結果
        if results:
            df_results = pd.DataFrame(results)[['id', 'name', 'status', 'close', 'ma5', 'ma10', 'pe', 'rsi']]
            df_results.columns = ['代號', '名稱', '狀態', '收盤價', 'MA5', 'MA10', 'PE', 'RSI']
            st.session_state['scan_results_ma5_breakout'] = df_results
            st.rerun()
        else:
            st.session_state['scan_results_ma5_breakout'] = pd.DataFrame()
            st.warning("未找到符合條件的股票")
    
    # 顯示結果
    ma5_results = st.session_state.get('scan_results_ma5_breakout')
    if ma5_results is not None and not ma5_results.empty:
        st.subheader(f"✅ 符合條件清單 ({len(ma5_results)})")
        df_show = ma5_results.sort_values(by='收盤價', ascending=False)
        event = st.dataframe(apply_table_style(df_show).hide(axis='index'), on_select="rerun", selection_mode="single-row",
                            use_container_width=True,
                            key=f"ma5_breakout_df_{st.session_state['dataframe_key']}")
        if len(event.selection.rows) > 0:
            idx = event.selection.rows[0]
            code_sel = df_show.iloc[idx]['代號']
            name_sel = df_show.iloc[idx]['名稱']
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔍 檢視個股體檢", key="ma5_to_detail"):
                    st.session_state['target_stock'] = code_sel
                    st.session_state['previous_page'] = "📈 MA5突破MA10掃描"
                    st.session_state['current_page'] = "🔍 單一個股體檢"
                    st.rerun()
            with col_b:
                if st.button("⭐ 加入觀察清單", key="ma5_to_watch"):
                    add_to_watchlist(code_sel, name_sel)
                    st.success(f"已加入觀察清單：{code_sel} {name_sel}")
    elif ma5_results is not None and ma5_results.empty:
        st.write("尚無符合條件的股票（請執行掃描）")
    else:
        st.write("請點擊「啟動掃描」開始掃描")

# ----------------- 頁面 D -----------------
elif mode == "📦 我持有的股票診斷":
    st.header("📦 我持有的股票診斷 (持股管理)")
    st.markdown("管理你的持股：新增、編輯、賣出並保存為歷史紀錄。資料會儲存在專案目錄下的 `holdings.json` 與 `history.json`。")

    # --- 檔案存放路徑 (使用模組層級已定義的 DATA_DIR，見第 325 行) ---
    HOLDINGS_FILE = os.path.join(DATA_DIR, 'holdings.json')
    HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')

    def load_json(path):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            return []
        return []

    def save_json(path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # Ensure session cache
    if 'holdings' not in st.session_state:
        st.session_state['holdings'] = load_json(HOLDINGS_FILE)
    if 'history' not in st.session_state:
        st.session_state['history'] = load_json(HISTORY_FILE)

    @st.cache_data(ttl=60)
    def get_latest_price(stock_id: str):
        try:
            df = yf.download(stock_id, period='1d', progress=False)
            if df is None or df.empty:
                return None
            # take last Close
            return float(df['Close'].iloc[-1])
        except Exception:
            return None

    # --- 新增持股表單 ---
    with st.expander('➕ 新增持股 / 調整現有持股', expanded=True):
        with st.form('add_holding_form'):
            col1, col2, col3 = st.columns(3)
            with col1:
                code_in = st.text_input('代號 (例如 2330.TW)')
                buy_date = st.date_input('買入日期')
            with col2:
                buy_price = st.number_input('買入價格 (每股)', min_value=0.0, format='%f')
                qty = st.number_input('股數', min_value=1, step=10, value=1000)
            with col3:
                note = st.text_input('備註 (選填)')
            submitted = st.form_submit_button('➕ 新增一筆持股')
            st.caption("💡 提示：輸入相同代號會視為新的一筆買入（分批進場）。若要修改舊庫存，請使用下方表格的『編輯』功能。")
            
            if submitted:
                if not code_in:
                    st.error('請輸入代號')
                else:
                    code_norm = normalize_stock_id(code_in)
                    # 支援分批買進：直接 Append，不覆蓋舊資料
                    st.session_state['holdings'].append({
                        'code': code_norm,
                        'buy_date': buy_date.strftime('%Y-%m-%d'),
                        'buy_price': float(buy_price),
                        'qty': int(qty),
                        'note': note
                    })
                    save_json(HOLDINGS_FILE, st.session_state['holdings'])
                    st.success('已新增一筆持股紀錄')

    st.markdown('---')

    # --- 顯示目前持股 ---
    holdings = st.session_state['holdings']
    if not holdings:
        st.info('目前沒有任何持股，請先新增。')
    else:
        rows = []
        for h in holdings:
            code = h.get('code')
            name = get_stock_display_name(code)
            buy_price = float(h.get('buy_price', 0.0))
            qty = int(h.get('qty', 0))
            latest = get_latest_price(code) or 0.0
            
            # 使用統一函式計算（預設 6 折手續費）
            log = calculate_tradelog(code, buy_price, latest, qty)
            total_cost = log['total_cost']
            net_value = log['net_value']
            unreal = log['unrealized_profit']
            pct = log['profit_pct']
            
            rows.append({
                '代號': code,
                '名稱': name,
                '買入日': h.get('buy_date'),
                '買入價': buy_price,
                '股數': qty,
                '成本(含費)': total_cost,
                '最新價': latest,
                '市值(扣費)': net_value,
                '未實現損益(元)': unreal,
                '未實現損益(%)': pct,
                '備註': h.get('note','')
            })

        # Allow analysis & recommendation based on existing analyze_stock()
        if 'holdings_analysis' not in st.session_state:
            st.session_state['holdings_analysis'] = {}

        def make_recommendation(res_obj):
            if res_obj is None:
                return ('無資料', None, '無法取得分析結果')
            score = float(res_obj.score or 0)
            reasons = list(res_obj.reasons or [])
            # chips signal
            try:
                if res_obj.chips_df is not None:
                    cs = detect_chip_switch(res_obj.chips_df)
                    if cs:
                        # NOTE: detect_chip_switch 返回 tuple (kind, prev_val, last_val)，不是 dict
                        kind = cs[0] if isinstance(cs, tuple) else cs.get('kind', '')
                        if '賣轉買' in kind or kind == 'sell_to_buy':
                            chip_note = '外資轉買'
                        elif '買轉賣' in kind or kind == 'buy_to_sell':
                            chip_note = '外資轉賣'
                        if chip_note:
                            reasons.append(chip_note)
            except Exception:
                pass

            if score >= 70:
                rec = '建議持有／加碼'
            elif score >= 40:
                rec = '觀察 (持有)'
            else:
                rec = '建議賣出'

            return (rec, score, '; '.join(reasons))

        st.subheader('目前持股')
        col_anl, _ = st.columns([1,4])
        with col_anl:
            if st.button('🔎 分析並建議操作（會抓即時資料，較慢）'):
                progress = st.progress(0)
                status = st.empty()
                analyses = {}
                for i, h in enumerate(holdings):
                    code = h.get('code')
                    status.text(f'分析 {code} ({i+1}/{len(holdings)})...')
                    res = analyze_stock(code, start_date, include_chips=True)
                    rec, score, reasons = make_recommendation(res)
                    analyses[code] = {'rec': rec, 'score': score, 'reasons': reasons}
                    progress.progress((i+1)/len(holdings))
                progress.empty(); status.empty()
                st.session_state['holdings_analysis'] = analyses
                st.success('分析完成')

        # display holdings table (recommendation shown separately)
        df_hold = pd.DataFrame(rows)

        try:
            total_cost = float(df_hold['成本(含費)'].sum())
            total_value = float(df_hold['市值(扣費)'].sum())
            total_unreal = float(df_hold['未實現損益(元)'].sum())
            total_pct = (total_unreal / total_cost * 100) if total_cost != 0 else 0.0
        except Exception:
            total_cost = total_value = total_unreal = total_pct = 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric('總成本(含費)', f"{total_cost:,.0f} 元")
        m2.metric('總市值(扣費)', f"{total_value:,.0f} 元", delta=f"{total_unreal:,.0f} 元")
        m3.metric('未實現淨損益', f"{total_unreal:,.0f} 元", delta=f"{total_pct:.2f}%")
        m4.metric('持股筆數', f"{len(df_hold)}")

        st.markdown('---')

        # Format display table for readability
        df_display = df_hold.copy()
        if '未實現損益(%)' in df_display.columns:
            pass

        st.subheader('目前持股列表')
        if not df_display.empty:
            styled_df = apply_table_style(df_display)
            st.dataframe(styled_df.hide(axis='index'), use_container_width=True, height=len(df_display) * 35 + 38)
        else:
            st.info("尚無持股資料")

        # 選擇持股以編輯或賣出 (改為支援多筆同代號持股辨識)
        # 使用 Index 與詳細資訊作為選項
        options_map = {}
        display_options = ['--']
        
        for idx, h in enumerate(st.session_state['holdings']):
            c = h.get('code')
            n = get_stock_display_name(c).split(' ')[-1] # 簡化名稱
            d = h.get('buy_date')
            p = float(h.get('buy_price', 0))
            q = int(h.get('qty', 0))
            
            # 顯示格式: "1. 2330.TW (2026-02-04 買入 @ $500, 1000股)"
            label = f"{idx+1}. {c} {n} ({d} 買入 @ {p}, {q}股)"
            display_options.append(label)
            options_map[label] = idx

        sel_label = st.selectbox('選擇要操作的持股', options=display_options)
        
        if sel_label and sel_label != '--':
            target_idx = options_map[sel_label]
            
            # 安全檢查
            if 0 <= target_idx < len(st.session_state['holdings']):
                selected = st.session_state['holdings'][target_idx]
                sel_code = selected.get('code') # 取得代號供後續查詢
                
                # 顯示分析/建議（單獨區塊，而非表格欄位）
                analyses = st.session_state.get('holdings_analysis', {})
                a = analyses.get(sel_code)
                with st.expander('🔔 分析結果與建議', expanded=True):
                    if a:
                        rec = a.get('rec', '')
                        score = float(a.get('score') or 0)
                        reasons = a.get('reasons') or ''
                        # color selection
                        if '賣' in rec or '出場' in rec or '建議賣出' in rec:
                            card_bg = '#ff4d4f'
                            emoji = '🛑'
                        elif '觀察' in rec or '持有' in rec:
                            card_bg = '#faad14'
                            emoji = '⚠️'
                        else:
                            card_bg = '#52c41a'
                            emoji = '✅'

                        col_rec, col_score = st.columns([3,1])
                        with col_rec:
                            st.markdown(
                                f"<div style='padding:14px;border-radius:8px;background:{card_bg};color:#fff;font-size:18px;font-weight:600'>"
                                f"{emoji} {rec}</div>", unsafe_allow_html=True)
                            # brief holding summary
                            try:
                                buy_p = float(selected.get('buy_price'))
                                qty_p = int(selected.get('qty'))
                                latest_p = get_latest_price(selected.get('code')) or 0.0
                                
                                # 使用統一函式計算
                                log_p = calculate_tradelog(selected.get('code'), buy_p, latest_p, qty_p)
                                unreal_p = log_p['unrealized_profit']
                                pct_p = log_p['profit_pct']
                                
                                st.markdown(f"**持股小結：** {selected.get('code')}  {get_stock_display_name(selected.get('code'))}  ")
                                st.markdown(f"買入價：{buy_p:.2f}，股數：{qty_p}，最新價：{latest_p:.2f}  ")
                                st.markdown(f"未實現：{unreal_p:,.0f} 元 ({pct_p:.2f}%)")
                            except Exception:
                                pass
                        with col_score:
                            st.markdown('**評分**')
                            pct = max(0.0, min(1.0, score/100.0))
                            st.progress(pct)
                            st.markdown(f"**{score:.1f}/100**")

                        st.markdown('---')
                        st.markdown('**建議理由**')
                        # reasons may be a semicolon-separated string
                        reason_list = [r.strip() for r in re.split(r";|\n|\\n", reasons) if r.strip()]
                        if reason_list:
                            for r in reason_list:
                                st.markdown(f"- {r}")
                        else:
                            st.markdown('無特定理由')
                    else:
                        st.info('此持股尚未分析，請按「分析並建議操作」以取得建議。')

                # 刪除此持股 (依據 Index 刪除，精確定位)
                if st.button('🗑 刪除此持股', type="secondary"):
                    # 使用 pop 移除特定 index 的持股
                    if 0 <= target_idx < len(st.session_state['holdings']):
                        removed = st.session_state['holdings'].pop(target_idx)
                        save_json(HOLDINGS_FILE, st.session_state['holdings'])
                        st.success(f"已刪除持股: {removed.get('code')} ({removed.get('buy_date')})")
                        st.rerun()

                st.markdown('**編輯持股**')
                with st.form('edit_holding'):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_buy_date = st.date_input('買入日期', value=pd.to_datetime(selected.get('buy_date')))
                        e_buy_price = st.number_input('買入價格', value=float(selected.get('buy_price')))
                    with e_col2:
                        e_qty = st.number_input('股數', value=int(selected.get('qty')), step=1, min_value=1)
                        e_note = st.text_input('備註', value=selected.get('note',''))
                    e_save = st.form_submit_button('更新持股')
                    if e_save:
                        selected.update({'buy_date': e_buy_date.strftime('%Y-%m-%d'), 'buy_price': float(e_buy_price), 'qty': int(e_qty), 'note': e_note})
                        save_json(HOLDINGS_FILE, st.session_state['holdings'])
                        st.success('已更新持股')

                st.markdown('**賣出紀錄 (紀錄為歷史資料)**')
                with st.form('sell_holding'):
                    s_col1, s_col2 = st.columns(2)
                    with s_col1:
                        sell_date = st.date_input('賣出日期')
                        sell_price = st.number_input('賣出價格', min_value=0.0, format='%f')
                    with s_col2:
                        sell_qty = st.number_input('股數 (預設為持有股數)', value=int(selected.get('qty')), step=1, min_value=1)
                        sell_note = st.text_input('備註 (選填)')
                    s_submit = st.form_submit_button('確認賣出並移至歷史')
                    if s_submit:
                        # create history record
                        buy_price = float(selected.get('buy_price'))
                        buy_date = selected.get('buy_date')
                        qty = int(sell_qty)
                        
                        # 使用統一函式計算賣出損益（僅供紀錄參考，歷史列表會重算）
                        # 這裡簡單紀錄即可，詳細由 history display handling
                        
                        rec = {
                            'code': selected.get('code'),
                            'name': get_stock_display_name(selected.get('code')),
                            'buy_date': buy_date,
                            'buy_price': buy_price,
                            'sell_date': sell_date.strftime('%Y-%m-%d'),
                            'sell_price': float(sell_price),
                            'qty': qty,
                            'note': sell_note
                        }
                        st.session_state['history'].append(rec)
                        
                        # reduce or remove holding
                        if qty >= int(selected.get('qty')):
                            # 賣出全部：依據 index 移除該筆持股
                            if 0 <= target_idx < len(st.session_state['holdings']):
                                st.session_state['holdings'].pop(target_idx)
                        else:
                            # 賣出部分：更新剩餘股數
                            selected['qty'] = int(selected.get('qty')) - qty
                            
                        save_json(HOLDINGS_FILE, st.session_state['holdings'])
                        save_json(HISTORY_FILE, st.session_state['history'])
                        st.success('已紀錄賣出，並移至歷史資料')

    st.markdown('---')
    
    # --- 計算歷史總損益 (含費用) ---
    history = st.session_state['history']
    total_realized_net = 0
    updated_history = []
    
    FEE_RATE = 0.001425
    TAX_RATE = 0.003
    
    if history:
        for h in history:
            b_p = float(h.get('buy_price', 0))
            s_p = float(h.get('sell_price', 0))
            q = int(h.get('qty', 0))
            code = h.get('code', '')
            
            # 使用統一函式計算歷史損益
            log = calculate_tradelog(code, b_p, s_p, q)
            realized_net = log['unrealized_profit']
            total_realized_net += realized_net
            
            updated_history.append({
                '股票代號': code,
                '股票名稱': h.get('name',''),
                '買入日期': h.get('buy_date'),
                '賣出日期': h.get('sell_date'),
                '買入單價': b_p,
                '賣出單價': s_p,
                '股數': q,
                '已實現淨損益': realized_net,
                '報酬率(%)': log['profit_pct'],
                '備註': h.get('note','')
            })
            
    # --- 顯示標題與總損益 ---
    profit_color = "#FF4B4B" if total_realized_net > 0 else "#00D964" if total_realized_net < 0 else "gray"
    profit_str = f"{total_realized_net:,.0f}"
    if total_realized_net > 0: profit_str = f"+{profit_str}"
    
    st.markdown(f"### 📜 歷史成交紀錄 <span style='color:{profit_color}; font-size: 0.9em; margin-left: 10px'>(累計已實現損益: {profit_str} 元)</span>", unsafe_allow_html=True)
    
    if not history:
        st.info('目前尚無歷史成交紀錄。')
    else:
        df_hist = pd.DataFrame(updated_history)
        # 直接套用樣式（apply_table_style 會處理數值格式與顏色）
        styled_hist = apply_table_style(df_hist.sort_values(by='賣出日期', ascending=False))
        st.dataframe(styled_hist.hide(axis='index'), use_container_width=True)

        # 支援編輯歷史紀錄
        hist_codes = [f"{i} | {r.get('code')}" for i,r in enumerate(history)]
        sel_hist = st.selectbox('選擇要編輯的歷史紀錄 (index | code)', options=['--']+hist_codes)
        if sel_hist and sel_hist != '--':
            idx = int(sel_hist.split('|')[0].strip())
            rec = st.session_state['history'][idx]
            with st.form(f'edit_history_{idx}'):
                he_col1, he_col2 = st.columns(2)
                with he_col1:
                    he_buy_date = st.text_input('買入日期', value=rec.get('buy_date'))
                    he_buy_price = st.number_input('買入價格', value=float(rec.get('buy_price')))
                with he_col2:
                    he_sell_date = st.text_input('賣出日期', value=rec.get('sell_date'))
                    he_sell_price = st.number_input('賣出價格', value=float(rec.get('sell_price')))
                he_note = st.text_input('備註', value=rec.get('note',''))
                he_save = st.form_submit_button('更新歷史紀錄')
                if he_save:
                    rec.update({'buy_date': he_buy_date, 'buy_price': float(he_buy_price), 'sell_date': he_sell_date, 'sell_price': float(he_sell_price), 'note': he_note})
                    # recalc realized
                    rec['realized_profit'] = (float(rec['sell_price']) - float(rec['buy_price'])) * int(rec.get('qty',1))
                    rec['realized_pct'] = ((float(rec['sell_price'])/float(rec['buy_price']) - 1) * 100) if float(rec['buy_price'])!=0 else None
                    save_json(HISTORY_FILE, st.session_state['history'])
                    st.success('已更新歷史紀錄')

            # 刪除此歷史紀錄
            if st.button('🗑 刪除此歷史紀錄', type="secondary", key=f"delete_history_{idx}"):
                st.session_state['history'].pop(idx)
                save_json(HISTORY_FILE, st.session_state['history'])
                st.success('已刪除該歷史紀錄')
                st.rerun()



# ----------------- 頁面 D：觀察清單 -----------------
elif mode == "⭐ 觀察清單":
    st.header("⭐ 觀察清單")
    st.markdown("從「🚀 全自動量化選股 (動態類股版)」選到的標的，可以加入這裡做追蹤與後續體檢。")

    watchlist = st.session_state.get('watchlist', [])

    if not watchlist:
        st.info("目前觀察清單是空的，可以先到「🚀 全自動量化選股」頁面，用動態類股掃描並加入標的。")
    else:
        codes = [w['code'] for w in watchlist]
        names = [w.get('name') or get_stock_display_name(w['code']) for w in watchlist]
        # 一次請求多檔最新價（帶快取 60 秒）
        price_map = fetch_latest_prices_batch(tuple(codes))
        latest_prices = [price_map.get(c) for c in codes]

        st.subheader("目前觀察清單")
        # 過多時摺疊：前 10 筆直接顯示，其餘收在「更多」
        SHOW_FIRST = 10
        if len(watchlist) <= SHOW_FIRST:
            rows_to_show = list(zip(codes, names, latest_prices))
            more_rows = []
        else:
            rows_to_show = list(zip(codes[:SHOW_FIRST], names[:SHOW_FIRST], latest_prices[:SHOW_FIRST]))
            more_rows = list(zip(codes[SHOW_FIRST:], names[SHOW_FIRST:], latest_prices[SHOW_FIRST:]))

        def _render_watch_row(idx: int, code: str, name: str, price, key_prefix: str):
            col_code, col_name, col_price, col_view, col_delete = st.columns([2, 3, 2, 1, 1])
            with col_code:
                st.write(f"**{code}**")
            with col_name:
                st.write(name)
            with col_price:
                st.write(f"${price:.2f}" if price is not None else "N/A")
            with col_view:
                if st.button("🔍", key=f"{key_prefix}_view_{idx}_{code}", help="檢視個股體檢", use_container_width=True):
                    st.session_state['target_stock'] = code
                    st.session_state['previous_page'] = "⭐ 觀察清單"
                    st.session_state['current_page'] = "🔍 單一個股體檢"
                    st.rerun()
            with col_delete:
                if st.button("🗑", key=f"{key_prefix}_del_{idx}_{code}", help="刪除此股票", use_container_width=True):
                    new_wl = [w for w in watchlist if w.get('code') != code]
                    st.session_state['watchlist'] = new_wl
                    if save_watchlist(new_wl):
                        st.success(f"已從觀察清單移除：{code} {name}")
                    else:
                        st.warning(f"已從清單移除，但寫入檔案失敗，請稍後再試。")
                    st.rerun()

        for idx, (code, name, price) in enumerate(rows_to_show):
            _render_watch_row(idx, code, name, price, "wl")

        if more_rows:
            with st.expander(f"📂 更多 ({len(more_rows)} 筆)", expanded=False):
                for idx, (code, name, price) in enumerate(more_rows):
                    _render_watch_row(SHOW_FIRST + idx, code, name, price, "wl_more")

elif mode == "🔍 單一個股體檢":
    col_h, col_b = st.columns([6, 1])
    with col_h: st.header("🔍 單一個股深度體檢")
    with col_b:
        if st.session_state.get('target_stock'):
            st.button("🔙 返回列表", on_click=go_back_logic, type="primary")

    current_target = st.session_state.get('target_stock')
    default_val = current_target if current_target else "2330.TW"
    input_code = st.text_input("輸入代號", value=default_val)
    
    if input_code:
        stock_id = normalize_stock_id(input_code)
        stock_name = STOCK_DB.get(stock_id, {}).get("name", stock_id)

        # 上方操作按鈕列：加入觀察清單
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("⭐ 加入觀察清單", key="single_add_watch"):
                add_to_watchlist(stock_id, stock_name)
                st.success(f"已加入觀察清單：{stock_id} {stock_name}")
        with col_btn2:
            st.write("")  # 預留未來其他操作
        
        with st.spinner(f"分析 {stock_id}..."):
            # 體檢模式：開啟籌碼抓取 (include_chips=True)
            res_obj = analyze_stock(stock_id, start_date, include_chips=True)
            if res_obj:
                render_deep_checkup_view(stock_name, stock_id, res_obj)
            else:
                st.error("查無資料")