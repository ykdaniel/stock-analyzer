# core/constants.py
from enum import Enum

class SectorType(str, Enum):
    SEMI = "半導體/IC設計"
    AI_PC = "AI/電腦週邊"
    TRADITIONAL = "傳產/重電/原物料"
    SHIPPING = "航運"
    FINANCE = "金融"
    COMPONENTS = "電子零組件/光電"
    MEMORY = "記憶體"

class PositionLevel(str, Enum):
    NO_POSITION = "No_Position"
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    FULL = "Full"

POSITION_ORDER = [
    PositionLevel.NO_POSITION,
    PositionLevel.LIGHT,
    PositionLevel.MEDIUM,
    PositionLevel.HEAVY,
    PositionLevel.FULL,
]

# 估值參數設定
PE_EXPENSIVE_THRESHOLD = 40    # PE > 40 一律視為「昂貴」
PE_REASONABLE_BASE = 25        # 基準合理 PE
PE_GROWTH_MULTIPLIER = 35      # 若成長率 > 30%，合理 PE 可上修至此值

# 風險策略參數
RISK_PCT_LIMIT = 0.02           # 單筆交易總資金風險上限 2%
MIN_REWARD_RISK_RATIO = 2.0     # 最小盈虧比要求
ATR_STOP_MULTIPLIER = 1.5       # ATR 停損乘數

SECTOR_LIST = {
    SectorType.SEMI: [
        "2330", "2454", "3231", "2303", "3443", "3661", "2379", "3034", "3529", "4966", "2338", "3014", "3035", "3006"
    ],
    SectorType.AI_PC: [
        "2382", "2324", "2356", "3231", "2376", "2308", "2357", "6669", "2352", "2383", "3005"
    ],
    SectorType.TRADITIONAL: [
        "1504", "1519", "1513", "1514", "1609", "2002"
    ],
    SectorType.SHIPPING: [
        "2603", "2609", "2615", "2606"
    ],
    SectorType.FINANCE: [
        "2881", "2882", "2891", "2886", "2884", "2892"
    ],
    SectorType.COMPONENTS: [
        "2308", "3008", "3042", "2327", "2492", "3037", "8046", "3189", "3406"
    ],
    SectorType.MEMORY: [
        "2408", "2344", "2337", "8299", "3260"
    ]
}

STOCK_DB = {
    # 半導體/IC設計
    "2330": {"name": "台積電", "sector": SectorType.SEMI},
    "2454": {"name": "聯發科", "sector": SectorType.SEMI},
    "3231": {"name": "緯創", "sector": SectorType.SEMI},
    "2303": {"name": "聯電", "sector": SectorType.SEMI},
    "3443": {"name": "創意", "sector": SectorType.SEMI},
    "3661": {"name": "世芯-KY", "sector": SectorType.SEMI},
    "2379": {"name": "瑞昱", "sector": SectorType.SEMI},
    "3034": {"name": "聯詠", "sector": SectorType.SEMI},
    "3529": {"name": "力旺", "sector": SectorType.SEMI},
    "4966": {"name": "譜瑞-KY", "sector": SectorType.SEMI},
    "2338": {"name": "光罩", "sector": SectorType.SEMI},
    "3014": {"name": "聯陽", "sector": SectorType.SEMI},
    "3035": {"name": "智原", "sector": SectorType.SEMI},
    "3006": {"name": "晶豪科", "sector": SectorType.SEMI},

    # AI/電腦週邊
    "2382": {"name": "廣達", "sector": SectorType.AI_PC},
    "2324": {"name": "仁寶", "sector": SectorType.AI_PC},
    "2356": {"name": "英業達", "sector": SectorType.AI_PC},
    "2376": {"name": "技嘉", "sector": SectorType.AI_PC},
    "2308": {"name": "台達電", "sector": SectorType.AI_PC},
    "2357": {"name": "華碩", "sector": SectorType.AI_PC},
    "6669": {"name": "緯穎", "sector": SectorType.AI_PC},
    "2352": {"name": "佳世達", "sector": SectorType.AI_PC},
    "2383": {"name": "台光電", "sector": SectorType.AI_PC},
    "3005": {"name": "神基", "sector": SectorType.AI_PC},

    # 傳產/重電/原物料
    "1504": {"name": "東元", "sector": SectorType.TRADITIONAL},
    "1519": {"name": "華城", "sector": SectorType.TRADITIONAL},
    "1513": {"name": "中興電", "sector": SectorType.TRADITIONAL},
    "1514": {"name": "亞力", "sector": SectorType.TRADITIONAL},
    "1609": {"name": "大亞", "sector": SectorType.TRADITIONAL},
    "2002": {"name": "中鋼", "sector": SectorType.TRADITIONAL},

    # 航運
    "2603": {"name": "長榮", "sector": SectorType.SHIPPING},
    "2609": {"name": "陽明", "sector": SectorType.SHIPPING},
    "2615": {"name": "萬海", "sector": SectorType.SHIPPING},
    "2606": {"name": "裕民", "sector": SectorType.SHIPPING},

    # 金融
    "2881": {"name": "富邦金", "sector": SectorType.FINANCE},
    "2882": {"name": "國泰金", "sector": SectorType.FINANCE},
    "2891": {"name": "中信金", "sector": SectorType.FINANCE},
    "2886": {"name": "兆豐金", "sector": SectorType.FINANCE},
    "2884": {"name": "玉山金", "sector": SectorType.FINANCE},
    "2892": {"name": "第一金", "sector": SectorType.FINANCE},

    # 電子零組件/光電
    "3008": {"name": "大立光", "sector": SectorType.COMPONENTS},
    "3042": {"name": "晶技", "sector": SectorType.COMPONENTS},
    "2327": {"name": "國巨", "sector": SectorType.COMPONENTS},
    "2492": {"name": "華新科", "sector": SectorType.COMPONENTS},
    "3037": {"name": "欣興", "sector": SectorType.COMPONENTS},
    "8046": {"name": "南電", "sector": SectorType.COMPONENTS},
    "3189": {"name": "景碩", "sector": SectorType.COMPONENTS},
    "3406": {"name": "玉晶光", "sector": SectorType.COMPONENTS},

    # 記憶體
    "2408": {"name": "南亞科", "sector": SectorType.MEMORY},
    "2344": {"name": "華邦電", "sector": SectorType.MEMORY},
    "2337": {"name": "旺宏", "sector": SectorType.MEMORY},
    "8299": {"name": "群聯", "sector": SectorType.MEMORY},
    "3260": {"name": "威剛", "sector": SectorType.MEMORY}
}
