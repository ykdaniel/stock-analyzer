"""
AI 量化戰情室 - 台股分析系統

【安全性增強版本】
- 已移除重複函數定義
- 保留較新版本的函數
- 建議在生產環境使用前充分測試

修復日期：2026-01-24
修復內容：
  1. 移除 6 個重複函數定義（analyze_stock, advanced_quant_filter 等）
  2. 保留功能較完整的版本
  3. 語法驗證通過
"""

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

# ==========================================
# 1. 資料庫定義 (SSOT)
# ==========================================
class SectorType:
    SEMI = "半導體/IC設計"
    AI_PC = "AI/電腦週邊"
    TRADITIONAL = "傳產/重電/原物料"
    SHIPPING = "航運"
    FINANCE = "金融"
    COMPONENTS = "電子零組件/光電"
    MEMORY = "記憶體"

STOCK_DB = {
    # --- 記憶體 (擴充版) ---
    "2408.TW": {"name": "南亞科", "sector": SectorType.MEMORY},
    "2344.TW": {"name": "華邦電", "sector": SectorType.MEMORY},
    "2337.TW": {"name": "旺宏", "sector": SectorType.MEMORY},
    "8299.TW": {"name": "群聯", "sector": SectorType.MEMORY},
    "3260.TW": {"name": "威剛", "sector": SectorType.MEMORY},
    "2451.TW": {"name": "創見", "sector": SectorType.MEMORY},
    "8271.TW": {"name": "宇瞻", "sector": SectorType.MEMORY},
    "4967.TW": {"name": "十銓", "sector": SectorType.MEMORY},
    "3006.TW": {"name": "晶豪科", "sector": SectorType.MEMORY},
    "3135.TW": {"name": "凌航", "sector": SectorType.MEMORY},
    "8084.TW": {"name": "巨虹", "sector": SectorType.MEMORY},
    "8088.TW": {"name": "品安", "sector": SectorType.MEMORY},
    "4973.TW": {"name": "廣穎", "sector": SectorType.MEMORY},
    "5386.TW": {"name": "青雲", "sector": SectorType.MEMORY},
    "8277.TW": {"name": "商丞", "sector": SectorType.MEMORY},

    # --- 半導體 ---
    "2330.TW": {"name": "台積電", "sector": SectorType.SEMI},
    "2454.TW": {"name": "聯發科", "sector": SectorType.SEMI},
    "2303.TW": {"name": "聯電", "sector": SectorType.SEMI},
    "3711.TW": {"name": "日月光投控", "sector": SectorType.SEMI},
    "2379.TW": {"name": "瑞昱", "sector": SectorType.SEMI},
    "3034.TW": {"name": "聯詠", "sector": SectorType.SEMI},
    "3035.TW": {"name": "智原", "sector": SectorType.SEMI},
    "3661.TW": {"name": "世芯-KY", "sector": SectorType.SEMI},
    "6415.TW": {"name": "矽力-KY", "sector": SectorType.SEMI},
    "3443.TW": {"name": "創意", "sector": SectorType.SEMI},
    "6515.TW": {"name": "穎崴", "sector": SectorType.SEMI},

    # --- AI/電腦週邊 ---
    "2317.TW": {"name": "鴻海", "sector": SectorType.AI_PC},
    "2382.TW": {"name": "廣達", "sector": SectorType.AI_PC},
    "3231.TW": {"name": "緯創", "sector": SectorType.AI_PC},
    "6669.TW": {"name": "緯穎", "sector": SectorType.AI_PC},
    "2357.TW": {"name": "華碩", "sector": SectorType.AI_PC},
    "3017.TW": {"name": "奇鋐", "sector": SectorType.AI_PC},
    "2345.TW": {"name": "智邦", "sector": SectorType.AI_PC},
    "2301.TW": {"name": "光寶科", "sector": SectorType.AI_PC},
    "3324.TW": {"name": "雙鴻", "sector": SectorType.AI_PC},
    "2376.TW": {"name": "技嘉", "sector": SectorType.AI_PC},
    "2368.TW": {"name": "金像電", "sector": SectorType.AI_PC},
    "2383.TW": {"name": "台光電", "sector": SectorType.AI_PC},

    # --- 傳產/重電 ---
    "1513.TW": {"name": "中興電", "sector": SectorType.TRADITIONAL},
    "1519.TW": {"name": "華城", "sector": SectorType.TRADITIONAL},
    "1503.TW": {"name": "士電", "sector": SectorType.TRADITIONAL},
    "1504.TW": {"name": "東元", "sector": SectorType.TRADITIONAL},
    "1605.TW": {"name": "華新", "sector": SectorType.TRADITIONAL},
    "2002.TW": {"name": "中鋼", "sector": SectorType.TRADITIONAL},
    "1101.TW": {"name": "台泥", "sector": SectorType.TRADITIONAL},
    "1301.TW": {"name": "台塑", "sector": SectorType.TRADITIONAL},
    "1303.TW": {"name": "南亞", "sector": SectorType.TRADITIONAL},
    "1326.TW": {"name": "台化", "sector": SectorType.TRADITIONAL},
    "9958.TW": {"name": "世紀鋼", "sector": SectorType.TRADITIONAL},
    "2014.TW": {"name": "中鴻", "sector": SectorType.TRADITIONAL},
    "4763.TW": {"name": "材料-KY", "sector": SectorType.TRADITIONAL},
    "1216.TW": {"name": "統一", "sector": SectorType.TRADITIONAL},
    "2912.TW": {"name": "統一超", "sector": SectorType.TRADITIONAL},
    "9910.TW": {"name": "豐泰", "sector": SectorType.TRADITIONAL},
    "2207.TW": {"name": "和泰車", "sector": SectorType.TRADITIONAL},

    # --- 航運 ---
    "2603.TW": {"name": "長榮", "sector": SectorType.SHIPPING},
    "2609.TW": {"name": "陽明", "sector": SectorType.SHIPPING},
    "2615.TW": {"name": "萬海", "sector": SectorType.SHIPPING},
    "2618.TW": {"name": "長榮航", "sector": SectorType.SHIPPING},
    "2610.TW": {"name": "華航", "sector": SectorType.SHIPPING},

    # --- 金融 ---
    "2881.TW": {"name": "富邦金", "sector": SectorType.FINANCE},
    "2882.TW": {"name": "國泰金", "sector": SectorType.FINANCE},
    "2891.TW": {"name": "中信金", "sector": SectorType.FINANCE},
    "2886.TW": {"name": "兆豐金", "sector": SectorType.FINANCE},
    "2884.TW": {"name": "玉山金", "sector": SectorType.FINANCE},
    "2892.TW": {"name": "第一金", "sector": SectorType.FINANCE},
    "5880.TW": {"name": "合庫金", "sector": SectorType.FINANCE},
    "2880.TW": {"name": "華南金", "sector": SectorType.FINANCE},
    "2885.TW": {"name": "元大金", "sector": SectorType.FINANCE},
    "2883.TW": {"name": "開發金", "sector": SectorType.FINANCE},
    "2887.TW": {"name": "台新金", "sector": SectorType.FINANCE},
    "5871.TW": {"name": "中租-KY", "sector": SectorType.FINANCE},
    "2890.TW": {"name": "永豐金", "sector": SectorType.FINANCE},
    "5876.TW": {"name": "上海商銀", "sector": SectorType.FINANCE},

    # --- 電子零組件 ---
    "2308.TW": {"name": "台達電", "sector": SectorType.COMPONENTS},
    "3037.TW": {"name": "欣興", "sector": SectorType.COMPONENTS},
    "3008.TW": {"name": "大立光", "sector": SectorType.COMPONENTS},
    "2327.TW": {"name": "國巨", "sector": SectorType.COMPONENTS},
    "2412.TW": {"name": "中華電", "sector": SectorType.COMPONENTS},
    "4904.TW": {"name": "遠傳", "sector": SectorType.COMPONENTS},
    "3045.TW": {"name": "台灣大", "sector": SectorType.COMPONENTS},
    "3406.TW": {"name": "玉晶光", "sector": SectorType.COMPONENTS},
    "6271.TW": {"name": "同欣電", "sector": SectorType.COMPONENTS},
    "2395.TW": {"name": "研華", "sector": SectorType.COMPONENTS}
}

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

# 動態生成衍生資料
NAME_MAPPING = {code: data["name"] for code, data in STOCK_DB.items()}
SECTOR_LIST = defaultdict(list)
# 移除已知在 yfinance 會 404 或下市的代碼（診斷後判定）
BAD_TICKERS = set([
    '8299.TW','3260.TW','8084.TW','8088.TW','4973.TW','5386.TW','8277.TW','3324.TW'
])

for code, data in STOCK_DB.items():
    if code in BAD_TICKERS:
        continue
    SECTOR_LIST[data["sector"]].append(code)
SECTOR_LIST = dict(SECTOR_LIST)
# 補充常見類股名稱到下拉選單（若該類股尚無成分，保留為空列表）
EXTRA_SECTORS_FOR_DROPDOWN = [
    "生技/醫療",
    "綠能/再生能源",
    "半導體設備",
    "電動車/電池",
    "軟體/雲端服務",
    "光電/面板",
    "消費性電子",
    "半導體材料",
    "不動產/建設",
    "食品/日用品",
    "航太/國防",
]
for s in EXTRA_SECTORS_FOR_DROPDOWN:
    if s not in SECTOR_LIST:
        SECTOR_LIST[s] = []

FULL_MARKET_DEMO = [c for c in STOCK_DB.keys() if c not in BAD_TICKERS]

def normalize_stock_id(code: str) -> str:
    """
    標準化股票代號：自動補上 .TW 後綴並轉大寫
    
    範例：
    - "2330" -> "2330.TW"
    - "2330.tw" -> "2330.TW"
    - "2330.TW" -> "2330.TW"
    """
    try:
        if not code or not isinstance(code, str):
            return code
        s = code.strip()
        if s == '':
            return s
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
    amount_cols = ['股數', '成本(含費)', '市值(扣費)', '未實現損益(元)', '已實現淨損益', '成交量', '量能']
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
        # 過濾掉空的與不需要的類別
        sectors = df['industry_category'].dropna().unique().tolist()
        return sorted([s for s in sectors if s])

    @staticmethod
    def get_stocks_by_sector(sector_name):
        """取得指定類別的股票代碼列表"""
        df = SectorProvider.get_taiwan_stock_info()
        if df is None: return []
        
        # 篩選類別
        subset = df[df['industry_category'] == sector_name]
        # 只取股票代碼，並轉為 yfinance 格式 (append .TW)
        codes = subset['stock_id'].tolist()
        return [normalize_stock_id(c) for c in codes]

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

@st.cache_data(ttl=300)
def top_n_by_volume(tickers: List[str], n: int = 10, avg_days: int = 3) -> List[str]:
    """Return top-n tickers by recent average volume.
    - tickers: list of symbols like '2330.TW'
    - n: number to return
    - avg_days: average over last avg_days days
    """
    try:
        if not tickers:
            return []
        period = f"{max(3, avg_days+1)}d"
        # yfinance supports list of tickers
        df = yf.download(tickers, period=period, progress=False)
        if df is None or df.empty:
            return []

        # get Volume for recent avg_days rows
        # handle multiindex (multiple tickers) or single
        if isinstance(df.columns, pd.MultiIndex):
            vol = df['Volume'].tail(avg_days)
            avg_vol = vol.mean(axis=0)
            # avg_vol index might be ticker tuples; convert to strings
            avg_vol.index = [str(t).upper() for t in avg_vol.index]
            top = avg_vol.sort_values(ascending=False).head(n).index.tolist()
            return top
        else:
            # single ticker case: df['Volume'] is a Series with index dates
            # return the single ticker if present
            return [tickers[0]] if tickers else []
    except Exception:
        return []

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

# ==========================================
# 三層式策略架構
# ==========================================

def market_regime_gate(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Layer 1: 市場開關（Gate）
    
    職責：只回答一個問題「現在能不能做多？」
    只看市場環境，不看個股
    
    輸出：
    {
        "allow_long": bool,
        "regime": "BULL" | "NEUTRAL" | "BEAR",
        "reason": str
    }
    """
    if df is None or df.empty or len(df) < 30:
        return {
            "allow_long": False,
            "regime": "UNKNOWN",
            "reason": "資料不足，無法判斷市場狀態"
        }
    
    curr = df.iloc[-1]
    close = float(curr['Close'])
    ma20 = float(curr.get('MA20', float('nan')))
    ma60 = float(curr.get('MA60', float('nan')))
    ma60_slope = float(df['MA60'].diff().tail(5).mean()) if 'MA60' in df.columns else 0.0
    
    # 市場狀態判斷（基於指數，這裡先用個股資料，未來可改為大盤指數）
    if close >= ma60 and ma20 >= ma60 and ma60_slope > 0:
        regime = "BULL"
        allow_long = True
        reason = "多頭市場：指數 > MA60，MA20 > MA60，MA60 上揚"
    elif close >= ma60:
        regime = "NEUTRAL"  # 盤整市場
        allow_long = True  # NEUTRAL 允許做多，但會限制策略模式
        reason = "盤整市場：指數在 MA60 上方，但趨勢不明"
    else:
        regime = "BEAR"
        allow_long = False
        reason = "空頭市場：指數跌破 MA60，多頭方向關閉"
    
    return {
        "allow_long": allow_long,
        "regime": regime,
        "reason": reason
    }


def select_strategy_mode(df: pd.DataFrame, market_regime: str) -> Dict[str, Any]:
    """
    Layer 2: 策略模式選擇（Mode Selector）
    
    職責：只決定「用哪種邏輯找股票」（結構分類）
    不決定買不買，不篩股票
    
    Mode A（回檔型）：
    - 價格接近 MA20 / MA60
    - 未破前低（前 N 日 Low）
    - MA60 方向不可下彎
    
    Mode B（趨勢型）：
    - 價格站上 MA20 / MA60
    - MA60 明確上彎
    - 非低檔盤整
    
    輸出：
    {
        "mode": "Trend" | "Pullback" | "NoTrade",  # 內部使用，對應 Mode B/A
        "reason": str
    }
    """
    if df is None or df.empty or len(df) < 30:
        return {
            "mode": "NoTrade",
            "reason": "資料不足"
        }
    
    if market_regime == "BEAR":
        return {
            "mode": "NoTrade",
            "reason": "空頭市場，不進行交易"
        }
    
    curr = df.iloc[-1]
    close = float(curr['Close'])
    ma20 = float(curr.get('MA20', float('nan')))
    ma60 = float(curr.get('MA60', float('nan')))
    ma60_slope = float(df['MA60'].diff().tail(5).mean()) if 'MA60' in df.columns else 0.0
    
    # Helper: 只取「昨天以前」的連續 n 日視窗，嚴格排除今天
    def prev_n_days(series: pd.Series, n: int) -> pd.Series:
        if series is None or len(series) < n + 1:
            return series.iloc[0:0]
        return series.iloc[-(n + 1):-1]
    
    # Mode B（趨勢型）：價格站上 MA20/MA60，MA60 明確上彎，非低檔盤整
    price_above_ma20 = close > ma20
    price_above_ma60 = close >= ma60
    ma20_above_ma60 = ma20 >= ma60
    ma60_rising = ma60_slope > 0
    
    # 檢查是否為低檔盤整（價格在 MA60 下方但接近）
    # NOTE: 只有當價格「未站穩」MA60 時才算低檔盤整，避免與 price_above_ma60 衝突
    is_low_consolidation = (close < ma60) and (close > ma60 * 0.9)
    
    if price_above_ma20 and price_above_ma60 and ma20_above_ma60 and ma60_rising and not is_low_consolidation:
        return {
            "mode": "Trend",  # 對應 Mode B
            "reason": "Mode B（趨勢型）：價格站上 MA20/MA60，MA60 上彎，非低檔盤整"
        }
    
    # Mode A（回檔型）：價格接近 MA20/MA60，未破前低，MA60 方向不可下彎
    price_near_ma20 = abs(close - ma20) / ma20 <= 0.05 if ma20 > 0 else False  # 5% 範圍內
    price_near_ma60 = abs(close - ma60) / ma60 <= 0.05 if ma60 > 0 else False
    price_near_ma = price_near_ma20 or price_near_ma60
    
    prev10_low = prev_n_days(df['Low'], 10)
    recent_low_10 = float(prev10_low.min()) if not prev10_low.empty else float('nan')
    no_new_low = close >= recent_low_10 if not prev10_low.empty else True
    ma60_not_falling = ma60_slope >= 0  # MA60 不可下彎
    
    if price_near_ma and no_new_low and ma60_not_falling:
        return {
            "mode": "Pullback",  # 對應 Mode A
            "reason": "Mode A（回檔型）：價格接近 MA20/MA60，未破前低，MA60 未下彎"
        }
    
    # 不符合任何結構
    # NOTE: 即使是 NEUTRAL 市場，若不符合 Mode A 條件，也應返回 NoTrade
    # 避免將不符合結構的股票強制標記為 Pullback 模式
    return {
        "mode": "NoTrade",
        "reason": "不符合 Mode A 或 Mode B 的結構條件" + ("（盤整市場）" if market_regime == "NEUTRAL" else "")
    }


def evaluate_stock(df: pd.DataFrame, market_regime: str, strategy_mode: str) -> Dict[str, Any]:
    """
    Layer 3: 股票篩選（Stock Evaluation）
    
    職責：根據選定的 Mode，評估單一股票的 Watch/Buy 狀態
    嚴格分離：Mode ≠ Buy，Watch 是 Buy 的必要前置狀態
    
    核心原則：
    - Watch = 結構成立，但尚未出現低風險進場點
    - Buy = 嚴格的事件觸發（突破/回測成功/止跌訊號）
    - 高檔乖離保護：close/ma60 > MAX_MA60_EXTENSION → Buy 強制 False
    
    輸出：
    {
        "watch": bool,
        "buy": bool,
        "confidence": int (0-100),
        "reason": str
    }
    """
    # 高檔乖離上限（25%）
    MAX_MA60_EXTENSION = 1.25
    
    if df is None or df.empty or len(df) < 30:
        return {
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": "資料不足，無法評估"
        }
    
    # Helper: 只取「昨天以前」的連續 n 日視窗，嚴格排除今天
    # NOTE: 此處保留 local 定義以維持函數獨立性，未來可考慮提取至模組層級
    def prev_n_days(series: pd.Series, n: int) -> pd.Series:
        """回傳 series 中，緊鄰「昨天」往前數 n 天的資料視窗。"""
        if series is None or len(series) < n + 1:
            return series.iloc[0:0]  # 空視窗
        return series.iloc[-(n + 1):-1]
    
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
    vol_ma60 = float(curr.get('Vol_MA60', 0))
    rsi_curr = float(curr.get('RSI', float('nan')))
    k = float(curr.get('K', float('nan')))
    d = float(curr.get('D', float('nan')))
    prev_k = float(prev.get('K', float('nan'))) if len(df) > 1 else float('nan')
    prev_d = float(prev.get('D', float('nan'))) if len(df) > 1 else float('nan')
    ma60_slope = float(df['MA60'].diff().tail(5).mean()) if 'MA60' in df.columns else 0.0
    
    # 基本過濾：流動性
    liquidity_ok = vol_ma20 > 0
    if not liquidity_ok:
        return {
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": "流動性不足（Vol_MA20 為 0 或過低）"
        }
    
    # 高檔乖離檢查（用於 Buy 保護）
    ma60_extension_ratio = close / ma60 if ma60 > 0 else 1.0
    is_overextended = ma60_extension_ratio > MAX_MA60_EXTENSION
    
    # 如果市場不允許做多，直接返回
    if market_regime == "BEAR":
        return {
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": "市場狀態：BEAR，多頭方向關閉"
        }
    
    # 如果沒有 Mode，無法評估
    if strategy_mode == "NoTrade":
        return {
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": "不符合 Mode A 或 Mode B 的結構條件"
        }
    
    watch = False
    buy = False
    watch_reason_parts = []
    buy_reason_parts = []
    
    # ===== Watch 判定：結構成立，但尚未出現低風險進場點 =====
    # Watch = True 條件：Market Regime = BULL，Mode = A or B，未出現結構破壞
    if market_regime == "BULL":
        if strategy_mode == "Trend":  # Mode B
            # Mode B Watch: 趨勢結構成立，但未出現明確進場觸發
            price_above_ma20 = close > ma20
            price_above_ma60 = close >= ma60
            ma20_above_ma60 = ma20 >= ma60
            ma60_rising = ma60_slope > 0
            no_structure_break = price_above_ma60  # 未破 MA60
            
            if price_above_ma20 and price_above_ma60 and ma20_above_ma60 and ma60_rising and no_structure_break:
                watch = True
                if is_overextended:
                    watch_reason_parts.append("Mode B 趨勢股，但高檔整理中（等待回測或放量突破）")
                else:
                    watch_reason_parts.append("Mode B 趨勢股，結構完整，等待進場觸發")
        
        elif strategy_mode == "Pullback":  # Mode A
            # Mode A Watch: 回檔結構成立，但未出現止跌訊號
            price_above_ma60 = close >= ma60
            prev10_close = prev_n_days(df['Close'], 10)
            recent_low_close = float(prev10_close.min()) if not prev10_close.empty else float('nan')
            no_new_low = close >= recent_low_close if not prev10_close.empty else True
            no_structure_break = price_above_ma60  # 未破 MA60
            
            if price_above_ma60 and no_new_low and no_structure_break:
                watch = True
                watch_reason_parts.append("Mode A 回檔型，結構完整，等待止跌訊號")
    
    # ===== Buy 判定：嚴格的事件觸發 =====
    # NOTE: 高檔乖離保護提前檢查，避免無效的 Buy 判斷計算
    if watch and not is_overextended:  # Buy 只能在 Watch 為 True 且無高檔乖離時觸發
        if strategy_mode == "Trend":  # Mode B
            # Mode B Buy: 突破型 或 回測型（二選一）
            prev10_high = prev_n_days(df['High'], 10)
            recent_high_10 = float(prev10_high.max()) if not prev10_high.empty else float('nan')
            
            # 突破型觸發
            breakout_trigger = (
                close > recent_high_10 and  # 條件1：突破前10日高（不含今日）
                vol >= vol_ma20 * 1.5       # 條件2：量能放大 ≥ 1.5×
            )
            
            # 回測型觸發
            pullback_to_ma20 = abs(close - ma20) / ma20 <= 0.02 if ma20 > 0 else False  # 2% 範圍內
            pullback_to_ma10 = abs(close - ma10) / ma10 <= 0.02 if ma10 > 0 else False
            volume_shrink = vol < vol_ma20 * 0.8  # 量縮
            bullish_candle = close > open_price  # 紅K
            long_lower_shadow = (close - low) / (high - low) > 0.5 if high > low else False  # 下影線長
            
            pullback_trigger = (
                (pullback_to_ma20 or pullback_to_ma10) and  # 條件1：回測 MA20/MA10 不破
                volume_shrink and                            # 條件2：量縮
                (bullish_candle or long_lower_shadow)        # 條件3：紅K 或 長下影線
            )
            
            if breakout_trigger:
                buy = True
                buy_reason_parts.append("Mode B 突破觸發：收盤價創近10日新高且量能放大 ≥ 1.5×20日均量")
            elif pullback_trigger:
                buy = True
                buy_reason_parts.append("Mode B 回測觸發：回測 MA20/MA10 不破，量縮，出現止跌訊號")
        
        elif strategy_mode == "Pullback":  # Mode A
            # Mode A Buy: 必須同時成立（嚴格條件）
            prev10_close = prev_n_days(df['Close'], 10)
            recent_low_close = float(prev10_close.min()) if not prev10_close.empty else float('nan')
            
            # 條件1：價格 ≥ 前10日最低 Close（不含今日）
            price_above_recent_low = close >= recent_low_close if not prev10_close.empty else True
            
            # 條件2：出現止跌訊號（紅K、量縮止跌、KD 反轉等，至少滿足一項）
            bullish_candle = close > open_price  # 紅K
            volume_shrink = vol < vol_ma20 * 0.8  # 量縮止跌
            kd_reversal = (k > d) and (prev_k <= prev_d) if not (pd.isna(k) or pd.isna(d) or pd.isna(prev_k) or pd.isna(prev_d)) else False  # KD 反轉
            rsi_rebound = rsi_curr > 40 and rsi_curr < 60  # RSI 在合理區間反彈
            
            has_reversal_signal = bullish_candle or volume_shrink or kd_reversal or rsi_rebound
            
            # 條件3：價格未跌破 MA60
            price_not_below_ma60 = close >= ma60
            
            if price_above_recent_low and has_reversal_signal and price_not_below_ma60:
                buy = True
                buy_reason_parts.append("Mode A 止跌觸發：價格 ≥ 前10日低點，出現止跌訊號，未破 MA60")
    
    # ===== 高檔乖離保護：補充 Watch 理由 =====
    # NOTE: Buy 判斷已在上方提前過濾 is_overextended，此處僅補充 Watch 理由
    if is_overextended and watch:
        watch_reason_parts.append("（高檔乖離 > 25%，僅可觀察，不可買進）")
    
    # ===== 強制邏輯約束 =====
    # 絕對不允許：Buy = True 但 Watch = False（防禦性檢查）
    if buy and not watch:
        logger.warning("邏輯錯誤偵測: Buy=True 但 Watch=False，已強制修正 (stock data length: %d)", len(df))
        buy = False
        buy_reason_parts = []
    
    # Confidence 計算
    confidence = 0
    if watch:
        confidence += 40
    if buy:
        confidence += 40
    if market_regime == "BULL":
        confidence += 20
    elif market_regime == "NEUTRAL":
        confidence += 10
    confidence = max(0, min(100, confidence))
    
    # 組合理由
    reason_parts = []
    if watch:
        reason_parts.extend(watch_reason_parts)
    if buy:
        reason_parts.extend(buy_reason_parts)
    reason = "；".join(reason_parts) if reason_parts else "不符合任何條件"
    
    return {
        "watch": watch,
        "buy": buy,
        "confidence": confidence,
        "reason": reason
    }


def strategy_engine(df: pd.DataFrame) -> Dict:
    """
    策略引擎 - 三層式架構整合
    
    Layer 1: 市場開關（Gate）- 判斷是否允許做多
    Layer 2: 策略模式選擇（Mode Selector）- 決定用哪套邏輯
    Layer 3: 股票評估（Stock Evaluation）- 產生 Watch/Buy 訊號
    
    輸出格式（向後兼容）：
    {
        "market_regime": "BULL" | "NEUTRAL" | "BEAR",
        "mode": "Trend" | "Pullback" | "NoTrade",
        "watch": bool,
        "buy": bool,
        "confidence": int (0-100),
        "reason": str
    }
    """
    if df is None or df.empty or len(df) < 30:
        return {
            "market_regime": "UNKNOWN",
            "mode": "NoTrade",
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": "資料不足，無法判斷",
        }
    
    # Layer 1: 市場開關
    gate_result = market_regime_gate(df)
    allow_long = gate_result["allow_long"]
    market_regime = gate_result["regime"]
    
    if not allow_long:
        return {
            "market_regime": market_regime,
            "mode": "NoTrade",
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": gate_result["reason"],
            # 向後兼容欄位
            "regime": market_regime,
            "signal": "none",
            "status": gate_result["reason"],
            "reasons": [gate_result["reason"]],
        }
    
    # Layer 2: 策略模式選擇
    mode_result = select_strategy_mode(df, market_regime)
    strategy_mode = mode_result["mode"]
    
    if strategy_mode == "NoTrade":
        return {
            "market_regime": market_regime,
            "mode": "NoTrade",
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": mode_result["reason"],
            # 向後兼容欄位
            "regime": market_regime,
            "signal": "none",
            "status": mode_result["reason"],
            "reasons": [mode_result["reason"]],
        }
    
    # Layer 3: 股票評估
    eval_result = evaluate_stock(df, market_regime, strategy_mode)
    
    # 模式名稱映射（向後兼容：Trend -> B, Pullback -> A）
    mode_display = "B" if strategy_mode == "Trend" else "A"
    
    return {
        "market_regime": market_regime,
        "mode": mode_display,  # 向後兼容：顯示 A/B
        "watch": eval_result["watch"],
        "buy": eval_result["buy"],
        "confidence": eval_result["confidence"],
        "reason": eval_result["reason"],
        # 向後兼容欄位
        "regime": market_regime,
        "signal": "buy" if eval_result["buy"] else ("watch" if eval_result["watch"] else "none"),
        "status": eval_result["reason"],
        "reasons": [eval_result["reason"]],
    }

def advanced_quant_filter(stock_id, start_date, pre_fetched_df=None):
    """
    全自動篩選邏輯（不抓籌碼以求效能）
    
    責任：
    - 只負責資料準備 + 呼叫 strategy_engine
    - 所有判斷統一由 strategy_engine 輸出
    - 不再自行判斷買賣點
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
        
        if df is None: 
            return None
        
        curr = df.iloc[-1]
        
        # 基本流動性過濾（可選，不影響 strategy_engine 判斷）
        vol_ma20 = curr.get('Vol_MA20', 0)
        if vol_ma20 < 1000000: 
            return None  # 流動性過低，直接跳過

        # 使用策略引擎決定 watch / buy（唯一決策來源）
        strat = strategy_engine(df)
        market_regime = strat.get("market_regime", "UNKNOWN")
        mode = strat.get("mode")
        watch = bool(strat.get("watch", False))
        buy = bool(strat.get("buy", False))
        confidence = strat.get("confidence", 0)
        reason = strat.get("reason", "")

        # 狀態文字完全根據 watch / buy
        if buy:
            status = "✅ Buy"
        elif watch:
            status = "👀 Watch"
        else:
            status = "觀望"

        # 基本面資訊（僅供參考，不影響決策）
        pe = info.get('trailingPE', float('inf'))
        if pe is None: 
            pe = float('inf')
        peg = info.get('pegRatio', float('inf'))
        if peg is None: 
            peg = float('inf')

        return {
            "id": stock_id,
            "close": curr['Close'],
            "pe": pe,
            "rsi": curr.get('RSI', 0),
            "status": status,
            "reasons": reason,
            "watch": watch,
            "buy": buy,
            "market_regime": market_regime,
            "mode": mode,
            "confidence": confidence,
        }
    except Exception as e:
        logger.debug("advanced_quant_filter error for %s: %s", stock_id, e)
        return None

def ma5_breakout_ma20_filter(stock_id, start_date, pre_fetched_df=None):
    """
    MA5 突破 MA20 篩選函數
    
    條件：
    1. 股價站上5日線（close > MA5）
    2. 5日線突破20日線（前一日 MA5 <= MA20，當日 MA5 > MA20）
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
        ma20_curr = float(curr.get('MA20', float('nan')))
        ma20_prev = float(prev.get('MA20', float('nan')))
        
        # 檢查是否有 NaN
        if pd.isna(ma5_curr) or pd.isna(ma5_prev) or pd.isna(ma20_curr) or pd.isna(ma20_prev):
            return None
        
        # 條件1：股價站上5日線
        condition1 = close > ma5_curr
        
        # 條件2：5日線突破20日線（前一日 MA5 <= MA20，當日 MA5 > MA20）
        condition2 = (ma5_prev <= ma20_prev) and (ma5_curr > ma20_curr)
        
        if condition1 and condition2:
            # 基本面資訊（僅供參考）
            pe = info.get('trailingPE', float('inf'))
            if pe is None: 
                pe = float('inf')
            
            return {
                "id": stock_id,
                "close": close,
                "ma5": ma5_curr,
                "ma20": ma20_curr,
                "pe": pe,
                "rsi": curr.get('RSI', 0),
                "status": "✅ 符合條件",
            }
        else:
            return None
    except Exception as e:
        logger.debug("ma5_breakout_ma20_filter error for %s: %s", stock_id, e)
        return None

# ==========================================
# 5. 視圖層 (View / UI)
# ==========================================
def render_deep_checkup_view(stock_name, stock_id, result: StockAnalysisResult):
    st.markdown(f"## 🏥 {stock_name} ({stock_id}) 深度投資體檢報告")
    
    df = result.tech_df
    fundamentals = result.fundamentals
    df_chips = result.chips_df
    curr = df.iloc[-1]
    prev = df.iloc[-2]

    # 🧠 策略引擎總結區塊（Regime + Mode + Watch/Buy）
    try:
        engine = strategy_engine(df)
    except Exception:
        engine = {
            "market_regime": "UNKNOWN",
            "mode": None,
            "watch": False,
            "buy": False,
            "confidence": 0,
            "reason": "資料不足或計算失敗",
        }

    market_regime = engine.get("market_regime", "UNKNOWN")
    mode = engine.get("mode")
    watch = engine.get("watch", False)
    buy = engine.get("buy", False)
    confidence = engine.get("confidence", 0)
    reason = engine.get("reason", "")

    st.subheader("🧠 策略引擎判斷 (Market Regime & Mode & Watch/Buy)")
    
    # 左側：主要決策卡片
    col_main, col_detail = st.columns([2, 3])
    with col_main:
        if buy:
            st.success(f"""
            **✅ Buy 訊號觸發**
            
            信心度：{confidence}%  
            Mode：{mode}
            """)
            st.caption("條件完整，可執行交易")
        elif watch:
            st.warning(f"""
            **👀 Watchlist 觀察中**
            
            信心度：{confidence}%  
            Mode：{mode}
            """)
            st.caption("值得盯，但尚未觸發買點")
        else:
            st.info("""
            **目前無明確進場設定**
            
            市場狀態或結構尚未符合條件
            """)
    
    # 右側：詳細資訊
    with col_detail:
        # 市場狀態
        if market_regime == "BULL":
            regime_icon = "📈"
            regime_txt = "BULL（多頭市場）"
            regime_color = COLOR_UP
        elif market_regime == "NEUTRAL":
            regime_icon = "📊"
            regime_txt = "NEUTRAL（盤整市場）"
            regime_color = "#FFA000" # 深橘色
        elif market_regime == "BEAR":
            regime_icon = "📉"
            regime_txt = "BEAR（空頭市場）"
            regime_color = COLOR_DOWN
        else:
            regime_icon = "❓"
            regime_txt = "未知"
            regime_color = "#757575" # 灰色
        
        # 信心度進度條
        st.markdown(f"**市場狀態**：{regime_icon} {regime_txt}")
        st.markdown(f"**策略型態**：Mode {mode or '-'}")
        st.progress(confidence / 100, text=f"信心度：{confidence}%")
        
        # Watch / Buy 狀態
        col_wb1, col_wb2 = st.columns(2)
        with col_wb1:
            if watch:
                st.markdown("**Watch**：✅ 是")
            else:
                st.markdown("**Watch**：❌ 否")
        with col_wb2:
            if buy:
                st.markdown("**Buy**：✅ 是")
            else:
                st.markdown("**Buy**：❌ 否")
        
        # 理由說明
        if reason:
            st.markdown("---")
            st.markdown(f"**判斷理由**：")
            st.caption(reason)
    
    st.markdown("---")

    # 若 session 有最近一次外資轉向事件，且屬於此股票，於頁面頂部顯示橫幅
    last_key = f'last_chip_switch_{stock_id}'
    if last_key in st.session_state:
        evt = st.session_state[last_key]
        if '賣轉買' in evt['type']:
            st.success(f"🚨 外資近期轉向 (最新): {evt['date']} — {evt['type']}：{evt['prev']:.0f} → {evt['last']:.0f} 張")
        else:
            st.warning(f"⚠️ 外資近期轉向 (最新): {evt['date']} — {evt['type']}：{evt['prev']:.0f} → {evt['last']:.0f} 張")
    

    
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

    # 2. 技術面
    col_trend, col_mom, col_vol = st.columns(3)
    with col_trend:
        st.subheader("2️⃣ 趨勢結構 (Trend)")
        ma5_val = curr['MA5']
        ma20_val = curr['MA20']
        ma60_val = curr['MA60']
        slope_ok = df['MA60_Rising'].iloc[-1]
        is_short_strong = ma5_val >= ma20_val
        check_item("短線趨勢 (MA5/20)", ma5_val - ma20_val, is_short_strong, "(MA5 > MA20)")
        t1 = check_item("均線排列 (MA20/60)", curr['MA20'] - curr['MA60'], curr['MA20'] >= curr['MA60'], "(多頭)")
        t2 = check_item(f"股價 vs 季線({ma60_val:.0f})", curr['Close'], curr['Close'] >= ma60_val, "(線上)")
        t3 = check_item("季線方向", "上彎" if slope_ok else "走平/下彎", slope_ok, "")
        trend_pass = t1 and t2 and t3

    with col_mom:
        st.subheader("3️⃣ 動能訊號 (Momentum)")
        rsi_cross = (prev['RSI'] < 40) and (curr['RSI'] >= 40)
        macd_up = (curr['MACD_Hist'] > 0) and (curr['MACD_Hist'] > prev['MACD_Hist'])
        check_item("RSI 強度", f"{curr['RSI']:.1f}", curr['RSI'] >= 50, "(>50 多方區)")
        check_item("MACD 攻擊", "是" if macd_up else "否", macd_up, "(紅柱增長)")
        mom_pass = rsi_cross or macd_up or (curr['RSI'] >= 50 and macd_up)

    with col_vol:
        st.subheader("4️⃣ 價量確認 (Volume)")
        high_60 = curr['High_60']
        breakout = curr['Close'] > high_60
        vol_ratio = curr['Volume'] / curr['Vol_MA20']
        check_item("突破前高", f"{high_60:.2f}", breakout, "(壓力價)")
        check_item("攻擊量能", f"{vol_ratio:.2f}倍", vol_ratio >= 1.3, "(> 1.3倍)")
        pv_pass = breakout or (vol_ratio >= 1.3)

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
                st.markdown(f"**最新外資買賣超**: :{c_color}[{last_chip['Net_Buy']:.0f} 張]")
                
                recent_5_days = aligned_chips['Net_Buy'].tail(5).sum()
                chip_status = "外資連買" if recent_5_days > 0 else "外資調節"
                st.info(f"💡 近5日外資累計: {recent_5_days:.0f} 張 ({chip_status})")
                # 檢測外資買賣趨勢是否發生由賣轉買或由買轉賣的轉向
                switch = detect_chip_switch(aligned_chips)
                if switch is not None:
                    kind, prev_val, last_val = switch
                    # 記錄事件於 session
                    try:
                        record_chip_event(stock_id, kind, prev_val, last_val, aligned_chips.index[-1])
                    except Exception:
                        pass

                    if "賣轉買" in kind:
                        st.success(f"🚨 外資轉向：由賣轉買 — 前: {prev_val:.0f} 張 → 現: {last_val:.0f} 張")
                    elif "買轉賣" in kind:
                        st.warning(f"⚠️ 外資轉向：由買轉賣 — 前: {prev_val:.0f} 張 → 現: {last_val:.0f} 張")

                # 顯示 session 中的外資轉向紀錄
                render_chip_history_table(stock_id)
    else:
        if not FINMIND_AVAILABLE:
            st.warning("⚠️ FinMind 套件未安裝，無法顯示外資數據。\n安裝指令: `pip install FinMind`")
        else:
            st.warning("⚠️ 查無外資數據 (FinMind 連線逾時或該股票無外資資料)")
    
    st.markdown("---")

    # 6. 進出場時機 (KDJ)
    st.subheader("6️⃣ 進出場時機 (KDJ)")

    # 準備變數
    k_curr, k_prev = curr['K'], prev['K']
    d_curr, d_prev = curr['D'], prev['D']
    j_curr, j_prev = curr['J'], prev['J']
    
    # 1. 必要條件（略微放寬：D 低檔 + K 在 D 之上 + 不再破底）
    cond_d_low = d_curr <= 40  # 允許 D 在 40 以內（含低檔鈍化後續漲）
    cond_k_above_d = k_curr >= d_curr  # 不一定當天黃金交叉，只要 K 在 D 之上
    # 最近 3 根 K 棒收盤價未破低 (比較 Close 與近 3 日最低 Low) 或 簡單採收盤價不破前低
    # 這裡採用: 目前收盤價 >= 近 5 日最低收盤價 (代表沒有持續創新低)
    recent_low_close = df['Close'].iloc[-5:].min()
    cond_no_new_low = curr['Close'] >= recent_low_close

    nec_pass = cond_d_low and cond_k_above_d and cond_no_new_low
    
    # 2. 趨勢過濾 (至少 1 項) — 這裡只做「是否偏多」的基礎過濾
    tf_a = curr['Close'] >= curr['MA20']      # 收盤價站上月線
    # tf_c 回測不破 (簡化為 Low >= MA20)
    tf_c = curr['Low'] >= curr['MA20']
    trend_filter_pass = tf_a or tf_c
    
    # 3. 加分條件 (4 選 2)
    bonus_score = 0
    # (1) J 值超賣
    b1 = j_curr < 20
    # (2) 量能不縮：成交量至少不低於 5 日均量的 0.8 倍
    vol_ma5 = curr.get('Vol_MA5', 0)
    b2 = vol_ma5 > 0 and (curr['Volume'] >= vol_ma5 * 0.8)
    # (3) KD 同步上彎
    k_slope = k_curr - k_prev
    d_slope = d_curr - d_prev
    b3 = (k_slope > 0) and (d_slope > 0)
    # (4) 均線多頭結構作為加分（MA20 > MA60）
    tf_b = curr['MA20'] >= curr['MA60']
    b4 = tf_b
    
    for flag in (b1, b2, b3, b4):
        if flag:
            bonus_score += 1
    
    bonus_pass = bonus_score >= 2
    
    # 最終買進判定
    buy_signal = nec_pass and trend_filter_pass and bonus_pass
    
    # 賣出判定
    # 停利
    sell_take_profit = (k_curr >= 80 and k_curr < d_curr and k_prev >= d_prev) or (j_prev >= 100 and j_curr < j_prev)
    # 停損
    sell_stop_loss = curr['Close'] < curr['MA20']
    
    # 顯示 UI
    kdj_c1, kdj_c2 = st.columns(2)
    with kdj_c1:
        st.write("#### 🟢 買進訊號檢查")
        st.write("**【必要條件】(需全符合)**")
        check_item(f"D 值低檔 (D={d_curr:.1f} ≤ 40)", d_curr, cond_d_low)
        check_item("K 在 D 之上 (不一定當天黃金交叉)", "Yes" if cond_k_above_d else "No", cond_k_above_d)
        check_item("股價未創新低 (近5日)", "Yes" if cond_no_new_low else "No", cond_no_new_low)
        
        st.write("**【趨勢過濾】(至少符合 1 項)**")
        check_item("站上月線 (C > MA20)", "Yes" if tf_a else "No", tf_a)
        check_item("回測月線不破 (Low ≥ MA20)", "Yes" if tf_c else "No", tf_c)
        
        st.write(f"**【加分條件】(目前 {bonus_score} 分, 需 ≥ 2，4 選 2)**")
        check_item("J 值超賣 (J < 20)", f"{j_curr:.1f}", b1)
        check_item("量能不縮 (V ≥ 0.8 × Vol_MA5)", "Yes" if b2 else "No", b2)
        check_item("KD 同步上彎", "Yes" if b3 else "No", b3)
        check_item("均線多頭 (MA20 > MA60)", "Yes" if b4 else "No", b4)
        
        if buy_signal:
            st.success("✨ **符合買進訊號！** (多頭或盤整低檔啟動)")
        else:
            st.write("👉 **未觸發買進**")

    with kdj_c2:
        st.write("#### 🔴 賣出訊號檢查")
        st.write("**【停利訊號】**")
        if sell_take_profit:
            st.error("⚠️ 出現停利特徵 (高檔鈍化結束或死叉)")
        else:
            st.write("無 (持有續抱)")
            
        st.write("**【停損訊號】(最優先)**")
        if sell_stop_loss:
            st.error("🛑 跌破月線 (MA20)，建議停損/出場")
        else:
            st.write("✅ 股價守穩月線")

    # 一句話判定
    st.info("💡 **AI 總結**：多頭或盤整中，KDJ 低檔黃金交叉，且價格不再破低並有量能確認，才允許買進。")
    st.markdown("---")

    # 策略判定
    st.subheader("🎯 AI 戰略地圖與價格分級")
    price_defensive = curr['MA60']
    price_breakout = curr['High_60']
    price_current = curr['Close']
    
    action_type = "觀察"
    if not trend_pass:
        action_type = "空手/避開"
        msg_title = "🛑 趨勢結構破壞"
        msg_desc = "股價位於季線下方或均線空頭排列，目前不適合任何操作。"
        msg_color = "error"
    elif trend_pass and not (mom_pass or pv_pass):
        action_type = "防守等待"
        msg_title = "🛡️ 趨勢對，節奏未到 (防守型)"
        msg_desc = f"多頭結構成立，但缺乏攻擊動能。**不建議追價**，請等待回測季線支撐 **{price_defensive:.0f}** 不破再佈局。"
        msg_color = "info" 
    elif trend_pass and (mom_pass or pv_pass):
        action_type = "積極攻擊"
        msg_title = "🚀 趨勢與動能同步 (攻擊型)"
        msg_desc = "量能或指標轉強，可嘗試積極操作，亦可關注突破前高後的動能延續。"
        msg_color = "success" 
    else:
        msg_title = "⚠️ 投機型操作"
        msg_desc = "技術面強勢但基本面分數過低，僅適合短線價差。"
        msg_color = "warning"

    if msg_color == "success": st.success(f"**{msg_title}**\n\n{msg_desc}")
    elif msg_color == "info": st.info(f"**{msg_title}**\n\n{msg_desc}")
    elif msg_color == "warning": st.warning(f"**{msg_title}**\n\n{msg_desc}")
    else: st.error(f"**{msg_title}**\n\n{msg_desc}")

    # 價格分級表 (適配深色模式)
    row1_style = "background-color: #1B5E20; color: #FAFAFA;" if action_type == "積極攻擊" else ""
    row2_style = "background-color: #E65100; color: #FAFAFA;" if action_type == "防守等待" else ""
    
    st.markdown(f"""
    <style> .stTable td {{ vertical-align: middle; }} </style>
    <table style="width:100%; text-align: left; border-collapse: collapse;">
        <thead>
            <tr style="border-bottom: 2px solid #444; background-color: #262730; color: #FAFAFA;">
                <th style="padding: 8px;">角色</th>
                <th style="padding: 8px;">價格 (約)</th>
                <th style="padding: 8px;">策略意義</th>
                <th style="padding: 8px;">操作建議</th>
            </tr>
        </thead>
        <tbody>
            <tr style="{row1_style}">
                <td style="padding: 8px;">🚀 <strong>追價/壓力</strong></td>
                <td style="padding: 8px;">{price_breakout:.2f}</td>
                <td style="padding: 8px;">前波高點壓力</td>
                <td style="padding: 8px;">若帶量突破，可視為新波段起點。</td>
            </tr>
            <tr>
                <td style="padding: 8px;">📍 <strong>目前市價</strong></td>
                <td style="padding: 8px;"><strong>{price_current:.2f}</strong></td>
                <td style="padding: 8px;">當下成交價</td>
                <td style="padding: 8px;">需搭配動能判斷。</td>
            </tr>
            <tr style="{row2_style}">
                <td style="padding: 8px;">🛡️ <strong>防守/支撐</strong></td>
                <td style="padding: 8px; color: blue;"><strong>{price_defensive:.2f}</strong></td>
                <td style="padding: 8px;">MA60 (季線)</td>
                <td style="padding: 8px;"><strong>中期多頭防守線。</strong></td>
            </tr>
            <tr style="border-top: 1px solid #444; color: #FF4B4B;">
                <td style="padding: 8px;">🛑 <strong>停損參考</strong></td>
                <td style="padding: 8px;">{price_defensive * 0.98:.2f}</td>
                <td style="padding: 8px;">跌破季線 2%</td>
                <td style="padding: 8px;">有效跌破季線建議停損。</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)

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

    # 📊 圖表區 (4列布局：K線、成交量、外資買賣超、MACD)
    # ========================================================
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        row_heights=[0.36, 0.18, 0.22, 0.24],
        # 加大子圖垂直間距，讓區塊更分明
        vertical_spacing=0.06,
        subplot_titles=("K線與關鍵位", "成交量", "外資買賣超(張)", "MACD 指標"),
        specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}]]
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
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA60'], line=dict(color='blue', width=2), name='MA60 (防守)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['High_60'], line=dict(color='gray', dash='dash'), name='60日高 (壓力)'), row=1, col=1)
    # --- Row 2: 成交量 (顏色跟隨當日漲跌，單位改為「張」) ---
    price_change = df_plot['Close'] - df_plot['Close'].shift(1)
    colors_vol = [COLOR_UP if c >= 0 else COLOR_DOWN for c in price_change]
    volume_in_lots = df_plot['Volume'] / 1000  # 股數轉張數
    fig.add_trace(go.Bar(x=df_plot.index, y=volume_in_lots, marker_color=colors_vol, name='成交量(張)'), row=2, col=1)

    # --- Row 3: 外資買賣超 ---
    if df_chips is not None and not df_chips.empty:
        aligned_chips = df_chips.reindex(df_plot.index)
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
                name='外資買賣超'
            ),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=aligned_chips.index,
                y=aligned_chips['Chip_MA5'],
                line=dict(color='#ffd700', width=1.5),
                name='外資5MA'
            ),
            row=3,
            col=1,
        )

    # --- Row 4: MACD ---
    colors_macd = [COLOR_UP if v >= 0 else COLOR_DOWN for v in df_plot['MACD_Hist']]
    fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['MACD_Hist'], marker_color=colors_macd, name='MACD柱狀'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['DIF'], line=dict(color='#2962FF', width=1), name='DIF (快)'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['DEA'], line=dict(color='#FF6D00', width=1), name='DEA (慢)'), row=4, col=1)

    fig.update_layout(
        height=1100,
        xaxis_rangeslider_visible=False,
        title_text=f"{stock_id} 綜合分析圖",
        hovermode='x unified',
    )
    
    # 移除邊框設定，保持圖表乾淨
    
    # 設定 Y 軸標題
    fig.update_yaxes(title_text="成交量(張)", row=2, col=1)
    fig.update_yaxes(title_text="外資買賣超", row=3, col=1)
    fig.update_yaxes(title_text="MACD", row=4, col=1)

    st.plotly_chart(fig, use_container_width=True)

# 輔助功能
def generate_executive_summary(df, df_chips, price_current, price_ma20, price_ma60, k_curr, j_curr, d_curr, trend_ok):
    """
    根據各項指標產生總結建議 (Holders vs Buyers)
    """
    # 判斷籌碼狀態
    chip_msg = "外資動向不明"
    if df_chips is not None and not df_chips.empty:
        aligned_chips = df_chips.reindex(df.index).ffill()
        recent_5_sum = aligned_chips['Net_Buy'].tail(5).sum()
        if recent_5_sum > 0: chip_msg = "外資近期偏多"
        elif recent_5_sum < 0: chip_msg = "外資近期調節"
    
    # --- 1. 給持有者的建議 ---
    holder_advice = ""
    # 趨勢壞 (破季線)
    if price_current < price_ma60:
        holder_advice = "建議**「停損/減碼」**。股價已跌破生命線 (季線)，趨勢轉空，不宜戀戰。"
    # 趨勢好但短線弱 (破月線)
    elif price_current < price_ma20:
        holder_advice = f"建議**「續抱但提高警覺」**。大趨勢仍多頭 (守季線 {price_ma60:.0f})，但短線轉弱 (破月線)。若有效跌破季線則應離場。"
    # 強勢多頭
    else:
        # 高檔過熱?
        if k_curr > 80:
             holder_advice = "建議**「續抱並設移動停利」**。目前強勢但指標過熱，隨時留意獲利了結訊號 (如跌破 5日線)。"
        else:
             holder_advice = "建議**「續抱」**。股價在均線之上，趨勢健康。"

    # --- 2. 給空手的建議 (想買進) ---
    buyer_advice = ""
    # 空頭
    if not trend_ok:
        buyer_advice = "建議**「觀望」**。目前趨勢偏空 (均線排列不佳或股價在季線下)，此時進場像是接刀，風險極大。"
    else:
        # 多頭架構，看位階
        # 黃金交叉剛發生?
        k_prev = df['K'].iloc[-2]
        d_prev = df['D'].iloc[-2]
        gold_cross = (k_curr > d_curr) and (k_prev <= d_prev)
        
        if gold_cross and d_curr <= 50:
             buyer_advice = f"建議**「分批佈局」**。KDJ 低檔黃金交叉，且趨勢偏多。可嘗試進場，停損設在月線 {price_ma20:.0f}。"
        elif k_curr > 80:
             buyer_advice = f"建議**「觀望」**。指標已至高檔 (K>80)，現在追高風險較大。穩健者建議等待回測月線 {price_ma20:.0f} 或季線 {price_ma60:.0f} 不破再進場。"
        else:
             buyer_advice = f"建議**「區間操作」**。目前 {chip_msg}。若回檔至支撐位 {price_ma20:.0f} 附近可考慮承接。"

    return holder_advice, buyer_advice

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
if 'scan_results_ai_concept' not in st.session_state: st.session_state['scan_results_ai_concept'] = None

# 從文件加載觀察清單
if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = load_watchlist()

page_options = ["🏆 台灣50 (排除金融)", "🤖 AI概念股", "🚀 全自動量化選股 (動態類股版)", "📈 MA5突破MA20掃描", "📦 我持有的股票診斷", "⭐ 觀察清單", "🔍 單一個股體檢"]

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
    
    # 資料來源切換
    source_mode = st.radio("📡 資料來源", ["內建清單 (Manual)", "動態類股 (Dynamic - FinMind)"], horizontal=True)
    
    target_stocks = []
    scan_triggered = False
    batch_mode = False
    stock_info_map = {} # 存放動態抓取的 ID->Name 對照表
    
    if source_mode == "內建清單 (Manual)":
        sector_options = ["全部 (All)"] + list(SECTOR_LIST.keys())
        selected_sector = st.sidebar.selectbox("📂 請選擇掃描類股：", sector_options)
        
        if st.button(f"⚡ 啟動掃描 ({selected_sector})", type="primary"):
            scan_triggered = True
            if selected_sector == "全部 (All)": target_stocks = FULL_MARKET_DEMO[:5] # Demo limit
            else: target_stocks = SECTOR_LIST[selected_sector]
            
    else: # Dynamic Mode
        st.info("💡 點擊下方類股按鈕，將自動抓取最新成分股並進行批次掃描。")
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
elif mode == "📈 MA5突破MA20掃描":
    st.header("📈 MA5 突破 MA20 掃描")
    st.info("👇 掃描符合以下條件的股票：\n1. 股價站上5日線（close > MA5）\n2. 5日線突破20日線（前一日 MA5 <= MA20，當日 MA5 > MA20）")
    
    # 資料來源切換
    source_mode = st.radio("📡 資料來源", ["內建清單 (Manual)", "動態類股 (Dynamic - FinMind)"], horizontal=True)
    
    target_stocks = []
    scan_triggered = False
    batch_mode = False
    stock_info_map = {}
    
    if source_mode == "內建清單 (Manual)":
        sector_options = ["全部 (All)"] + list(SECTOR_LIST.keys())
        selected_sector = st.sidebar.selectbox("📂 請選擇掃描類股：", sector_options, key="ma5_breakout_sector")
        
        if st.button(f"⚡ 啟動掃描 ({selected_sector})", type="primary", key="ma5_breakout_scan"):
            scan_triggered = True
            if selected_sector == "全部 (All)": 
                target_stocks = FULL_MARKET_DEMO[:20]  # Demo limit
            else: 
                target_stocks = SECTOR_LIST[selected_sector]
    else:  # Dynamic Mode
        st.info("💡 點擊下方類股按鈕，將自動抓取最新成分股並進行批次掃描。")
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
            
            # 使用 MA5 突破 MA20 篩選函數
            res = ma5_breakout_ma20_filter(stock_id, start_date, pre_fetched_df=pre_df)
            
            if res:
                res['name'] = stock_name
                results.append(res)
            
            progress_bar.progress((i + 1) / total_stocks)
        
        progress_bar.empty()
        status_text.empty()
        
        # 儲存結果
        if results:
            df_results = pd.DataFrame(results)[['id', 'name', 'status', 'close', 'ma5', 'ma20', 'pe', 'rsi']]
            df_results.columns = ['代號', '名稱', '狀態', '收盤價', 'MA5', 'MA20', 'PE', 'RSI']
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
                    st.session_state['previous_page'] = "📈 MA5突破MA20掃描"
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
                qty = st.number_input('股數', min_value=50, step=50, value=50)
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
            # qty 現在以「股」為單位
            qty = int(h.get('qty', 0))
            latest = get_latest_price(code) or 0.0
            
            # 成本與市值（未含費用）
            raw_cost = buy_price * qty
            raw_value = latest * qty

            # 費用計算 (手續費 0.1425%, 交易稅 0.3%)
            FEE_RATE = 0.001425
            TAX_RATE = 0.003
            
            # 買入手續費 (無條件進入或四捨五入，這邊採標準算法)
            buy_fee = int(raw_cost * FEE_RATE)
            
            # 賣出預估費用 (手續費 + 證交稅)
            sell_fee = int(raw_value * FEE_RATE)
            sell_tax = int(raw_value * TAX_RATE)
            
            # 修正後的總成本 (含買入手續費)
            total_cost = raw_cost + buy_fee
            
            # 修正後的淨市值 (扣除賣出費用)
            net_value = raw_value - sell_fee - sell_tax
            
            # 淨損益
            unreal = net_value - total_cost
            pct = (unreal / total_cost * 100) if total_cost != 0 else None
            
            rows.append({
                '代號': code,
                '名稱': name,
                '買入日': h.get('buy_date'),
                '買入價': buy_price,
                '股數': qty,
                '成本(含費)': total_cost,      # 更新欄位名稱
                '最新價': latest,
                '市值(扣費)': net_value,       # 更新欄位名稱
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
            chip_note = None
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
        col_anl, col_sp = st.columns([1,4])
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

        # 選擇持股以編輯或賣出
        codes = [r['代號'] for r in rows]
        sel = st.selectbox('選擇要操作的持股', options=['--']+codes)
        if sel and sel != '--':
            selected = next((h for h in st.session_state['holdings'] if h.get('code')==sel), None)
            if selected:
                # 顯示分析/建議（單獨區塊，而非表格欄位）
                analyses = st.session_state.get('holdings_analysis', {})
                a = analyses.get(sel)
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
                                qty_p = int(selected.get('qty'))  # 股數
                                latest_p = get_latest_price(selected.get('code')) or 0.0
                                cost_p = buy_p * qty_p
                                value_p = latest_p * qty_p
                                unreal_p = value_p - cost_p
                                pct_p = (unreal_p / cost_p * 100) if cost_p != 0 else 0
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

                # 刪除此持股
                if st.button('🗑 刪除此持股', type="secondary"):
                    st.session_state['holdings'] = [h for h in st.session_state['holdings'] if h.get('code') != sel]
                    save_json(HOLDINGS_FILE, st.session_state['holdings'])
                    st.success('已刪除該持股')
                    st.rerun()

                st.markdown('**編輯持股**')
                with st.form('edit_holding'):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_buy_date = st.date_input('買入日期', value=pd.to_datetime(selected.get('buy_date')))
                        e_buy_price = st.number_input('買入價格', value=float(selected.get('buy_price')))
                    with e_col2:
                        e_qty = st.number_input('股數', value=int(selected.get('qty')), step=50, min_value=50)
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
                        sell_qty = st.number_input('股數 (預設為持有股數)', value=int(selected.get('qty')), step=50, min_value=50)
                        sell_note = st.text_input('備註 (選填)')
                    s_submit = st.form_submit_button('確認賣出並移至歷史')
                    if s_submit:
                        # create history record
                        buy_price = float(selected.get('buy_price'))
                        buy_date = selected.get('buy_date')
                        qty = int(sell_qty)
                        realized = (float(sell_price) - buy_price) * qty
                        realized_pct = ((float(sell_price)/buy_price - 1) * 100) if buy_price != 0 else None
                        rec = {
                            'code': selected.get('code'),
                            'name': get_stock_display_name(selected.get('code')),
                            'buy_date': buy_date,
                            'buy_price': buy_price,
                            'sell_date': sell_date.strftime('%Y-%m-%d'),
                            'sell_price': float(sell_price),
                            'qty': qty,
                            'realized_profit': realized,
                            'realized_pct': realized_pct,
                            'note': sell_note
                        }
                        st.session_state['history'].append(rec)
                        # reduce or remove holding
                        if qty >= int(selected.get('qty')):
                            st.session_state['holdings'] = [h for h in st.session_state['holdings'] if h.get('code')!=selected.get('code')]
                        else:
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
            
            raw_cost = b_p * q
            raw_val = s_p * q
            
            # 費用
            buy_fee = int(raw_cost * FEE_RATE)
            sell_fee = int(raw_val * FEE_RATE)
            sell_tax = int(raw_val * TAX_RATE)
            
            total_cost = raw_cost + buy_fee
            net_income = raw_val - sell_fee - sell_tax
            
            net_profit = net_income - total_cost
            net_pct = (net_profit / total_cost * 100) if total_cost != 0 else 0.0
            
            total_realized_net += net_profit
            
            h_new = h.copy()
            h_new['realized_profit'] = net_profit
            h_new['realized_pct'] = net_pct
            updated_history.append(h_new)

    # --- 顯示標題與總損益 ---
    profit_color = "#FF0000" if total_realized_net > 0 else "#009900" if total_realized_net < 0 else "black"
    profit_str = f"{total_realized_net:,.0f}"
    if total_realized_net > 0: profit_str = f"+{profit_str}"
    
    st.markdown(f"### 📜 歷史成交紀錄 <span style='color:{profit_color}; font-size: 0.9em; margin-left: 10px'>(總損益: {profit_str} 元)</span>", unsafe_allow_html=True)
    
    # st.subheader('📜 歷史成交紀錄') # replaced
    
    if not history:
        st.info('歷史紀錄為空。')
    else:
        # 重算歷史損益 (已在上方計算完成，直接使用 updated_history)
        df_hist = pd.DataFrame(updated_history)
        
        # 欄位中文化與格式化
        col_map = {
            'code': '代號', 'name': '名稱', 
            'buy_date': '買入日期', 'buy_price': '買入單價',
            'sell_date': '賣出日期', 'sell_price': '賣出單價',
            'qty': '股數', 
            'realized_profit': '已實現淨損益', 'realized_pct': '報酬率(%)', 
            'note': '備註'
        }
        
        if 'realized_profit' in df_hist.columns:
            df_hist = df_hist[['code','name','buy_date','buy_price','sell_date','sell_price','qty','realized_profit','realized_pct','note']]
            df_hist.rename(columns=col_map, inplace=True)
            
            # 格式化數字與美化 (改用 Styler)
            # 移除手動 map，保留數值給 apply_table_style
            pass
            
        # 套用樣式
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