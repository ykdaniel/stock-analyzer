# core/constants.py
from collections import defaultdict
from enum import Enum


class SectorType(str, Enum):
    SEMI        = "半導體/IC設計"
    AI_PC       = "AI/電腦週邊"
    TRADITIONAL = "傳產/重電/原物料"
    SHIPPING    = "航運"
    FINANCE     = "金融"
    COMPONENTS  = "電子零組件/光電"
    MEMORY      = "記憶體"


class PositionLevel(str, Enum):
    NO_POSITION = "No_Position"
    LIGHT       = "Light"
    MEDIUM      = "Medium"
    HEAVY       = "Heavy"
    FULL        = "Full"


POSITION_ORDER = [
    PositionLevel.NO_POSITION,
    PositionLevel.LIGHT,
    PositionLevel.MEDIUM,
    PositionLevel.HEAVY,
    PositionLevel.FULL,
]

# 估值參數設定
PE_EXPENSIVE_THRESHOLD = 40    # PE > 40 一律視為「昂貴」
PE_REASONABLE_BASE     = 25    # 基準合理 PE
PE_GROWTH_MULTIPLIER   = 35    # 若成長率 > 30%，合理 PE 可上修至此值

# 風險策略參數
RISK_PCT_LIMIT      = 0.02   # 單筆交易總資金風險上限 2%
ATR_STOP_MULTIPLIER = 1.5    # ATR 停損乘數

# ==============================================
# 股票資料庫（以 .TW 後綴, 對應 yfinance 格式）
# ==============================================
STOCK_DB = {
    # --- 記憶體 ---
    "2408.TW": {"name": "南亞科",  "sector": SectorType.MEMORY},
    "2344.TW": {"name": "華邦電",  "sector": SectorType.MEMORY},
    "2337.TW": {"name": "旺宏",    "sector": SectorType.MEMORY},
    "2451.TW": {"name": "創見",    "sector": SectorType.MEMORY},
    "8271.TW": {"name": "宇瞻",    "sector": SectorType.MEMORY},
    "4967.TW": {"name": "十銓",    "sector": SectorType.MEMORY},
    "3006.TW": {"name": "晶豪科",  "sector": SectorType.MEMORY},
    "3135.TW": {"name": "凌航",    "sector": SectorType.MEMORY},

    # --- 半導體/IC設計 ---
    "2330.TW": {"name": "台積電",     "sector": SectorType.SEMI},
    "2454.TW": {"name": "聯發科",     "sector": SectorType.SEMI},
    "2303.TW": {"name": "聯電",       "sector": SectorType.SEMI},
    "3711.TW": {"name": "日月光投控", "sector": SectorType.SEMI},
    "2379.TW": {"name": "瑞昱",       "sector": SectorType.SEMI},
    "3034.TW": {"name": "聯詠",       "sector": SectorType.SEMI},
    "3035.TW": {"name": "智原",       "sector": SectorType.SEMI},
    "3661.TW": {"name": "世芯-KY",    "sector": SectorType.SEMI},
    "6415.TW": {"name": "矽力-KY",    "sector": SectorType.SEMI},
    "3443.TW": {"name": "創意",       "sector": SectorType.SEMI},
    "6515.TW": {"name": "穎崴",       "sector": SectorType.SEMI},

    # --- AI/電腦週邊 ---
    "2317.TW": {"name": "鴻海",   "sector": SectorType.AI_PC},
    "2382.TW": {"name": "廣達",   "sector": SectorType.AI_PC},
    "3231.TW": {"name": "緯創",   "sector": SectorType.AI_PC},
    "6669.TW": {"name": "緯穎",   "sector": SectorType.AI_PC},
    "2357.TW": {"name": "華碩",   "sector": SectorType.AI_PC},
    "3017.TW": {"name": "奇鋐",   "sector": SectorType.AI_PC},
    "2345.TW": {"name": "智邦",   "sector": SectorType.AI_PC},
    "2301.TW": {"name": "光寶科", "sector": SectorType.AI_PC},
    "2376.TW": {"name": "技嘉",   "sector": SectorType.AI_PC},
    "2368.TW": {"name": "金像電", "sector": SectorType.AI_PC},
    "2383.TW": {"name": "台光電", "sector": SectorType.AI_PC},

    # --- 傳產/重電/原物料 ---
    "1513.TW": {"name": "中興電",   "sector": SectorType.TRADITIONAL},
    "1519.TW": {"name": "華城",     "sector": SectorType.TRADITIONAL},
    "1503.TW": {"name": "士電",     "sector": SectorType.TRADITIONAL},
    "1504.TW": {"name": "東元",     "sector": SectorType.TRADITIONAL},
    "1605.TW": {"name": "華新",     "sector": SectorType.TRADITIONAL},
    "2002.TW": {"name": "中鋼",     "sector": SectorType.TRADITIONAL},
    "1101.TW": {"name": "台泥",     "sector": SectorType.TRADITIONAL},
    "1301.TW": {"name": "台塑",     "sector": SectorType.TRADITIONAL},
    "1303.TW": {"name": "南亞",     "sector": SectorType.TRADITIONAL},
    "1326.TW": {"name": "台化",     "sector": SectorType.TRADITIONAL},
    "9958.TW": {"name": "世紀鋼",   "sector": SectorType.TRADITIONAL},
    "2014.TW": {"name": "中鴻",     "sector": SectorType.TRADITIONAL},
    "4763.TW": {"name": "材料-KY",  "sector": SectorType.TRADITIONAL},
    "1216.TW": {"name": "統一",     "sector": SectorType.TRADITIONAL},
    "2912.TW": {"name": "統一超",   "sector": SectorType.TRADITIONAL},
    "9910.TW": {"name": "豐泰",     "sector": SectorType.TRADITIONAL},
    "2207.TW": {"name": "和泰車",   "sector": SectorType.TRADITIONAL},

    # --- 航運 ---
    "2603.TW": {"name": "長榮",   "sector": SectorType.SHIPPING},
    "2609.TW": {"name": "陽明",   "sector": SectorType.SHIPPING},
    "2615.TW": {"name": "萬海",   "sector": SectorType.SHIPPING},
    "2618.TW": {"name": "長榮航", "sector": SectorType.SHIPPING},
    "2610.TW": {"name": "華航",   "sector": SectorType.SHIPPING},

    # --- 金融 ---
    "2881.TW": {"name": "富邦金",   "sector": SectorType.FINANCE},
    "2882.TW": {"name": "國泰金",   "sector": SectorType.FINANCE},
    "2891.TW": {"name": "中信金",   "sector": SectorType.FINANCE},
    "2886.TW": {"name": "兆豐金",   "sector": SectorType.FINANCE},
    "2884.TW": {"name": "玉山金",   "sector": SectorType.FINANCE},
    "2892.TW": {"name": "第一金",   "sector": SectorType.FINANCE},
    "5880.TW": {"name": "合庫金",   "sector": SectorType.FINANCE},
    "2880.TW": {"name": "華南金",   "sector": SectorType.FINANCE},
    "2885.TW": {"name": "元大金",   "sector": SectorType.FINANCE},
    "2883.TW": {"name": "開發金",   "sector": SectorType.FINANCE},
    "2887.TW": {"name": "台新金",   "sector": SectorType.FINANCE},
    "5871.TW": {"name": "中租-KY",  "sector": SectorType.FINANCE},
    "2890.TW": {"name": "永豐金",   "sector": SectorType.FINANCE},
    "5876.TW": {"name": "上海商銀", "sector": SectorType.FINANCE},

    # --- 電子零組件/光電 ---
    "2308.TW": {"name": "台達電", "sector": SectorType.COMPONENTS},
    "3037.TW": {"name": "欣興",   "sector": SectorType.COMPONENTS},
    "3008.TW": {"name": "大立光", "sector": SectorType.COMPONENTS},
    "2327.TW": {"name": "國巨",   "sector": SectorType.COMPONENTS},
    "2412.TW": {"name": "中華電", "sector": SectorType.COMPONENTS},
    "4904.TW": {"name": "遠傳",   "sector": SectorType.COMPONENTS},
    "3045.TW": {"name": "台灣大", "sector": SectorType.COMPONENTS},
    "3406.TW": {"name": "玉晶光", "sector": SectorType.COMPONENTS},
    "6271.TW": {"name": "同欣電", "sector": SectorType.COMPONENTS},
    "2395.TW": {"name": "研華",   "sector": SectorType.COMPONENTS},
}

# 已知在 yfinance 會 404 或下市的代碼（明確從 SECTOR_LIST 排除）
BAD_TICKERS = {
    "8084.TW", "8088.TW", "4973.TW", "5386.TW", "8277.TW",
}

# 依 STOCK_DB 動態生成各板塊成分股列表
_sector_list: dict = defaultdict(list)
for _code, _data in STOCK_DB.items():
    if _code not in BAD_TICKERS:
        _sector_list[_data["sector"]].append(_code)
SECTOR_LIST: dict = dict(_sector_list)

# 補充常見類股名稱（供下拉選單使用；若無成分維持空列表）
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
