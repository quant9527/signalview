"""信号系列常量：前缀用于 startswith / SQL LIKE；全名列表用于 isin 等。"""

# ---------------------------------------------------------------------------
# 前缀（与库表 signal_name 一致）
# ---------------------------------------------------------------------------
NESTED_2BC_PREFIX: str = "nested_2bc"
PAIR_SEG_PREFIX: str = "pair_seg"
CL3B_MACD_PREFIX: str = "cl3b_macd"
CL3B_ZSX_PREFIX: str = "cl3b_zsx"
CMP_PREFIX: str = "cmp"

# ---------------------------------------------------------------------------
# nested_2bc 已知全名（可按库内实际继续追加）
# ---------------------------------------------------------------------------
NESTED_2BC_SIGNAL_NAMES: list[str] = [
    "nested_2bc_macd_1b",
    "nested_2bc_ma5ma10_1b",
]

# ---------------------------------------------------------------------------
# CMP（同花顺板块等）— 全名列表
# ---------------------------------------------------------------------------
CMP_SIGNAL_NAMES: list[str] = [
    "cmp_rebound_pioneer_ma5ma10",
    "cmp_zs_macd",
    "cmp_xsx_ma5ma10",
    "cmp_xsx_macd",
]

# ---------------------------------------------------------------------------
# 全局预拉：侧边栏 df 若缺某系列则按前缀补 load（多页共用）
# ---------------------------------------------------------------------------
SIGNAL_NAME_PREFIXES_PRELOAD: tuple[str, ...] = (
    NESTED_2BC_PREFIX,
    PAIR_SEG_PREFIX,
    CL3B_MACD_PREFIX,
    CL3B_ZSX_PREFIX,
    CMP_PREFIX,
)

# ---------------------------------------------------------------------------
# Performance 页「功能」默认勾选用的前缀组合
# ---------------------------------------------------------------------------
PERFORMANCE_PRESET_AS_PREFIXES: tuple[str, ...] = (
    NESTED_2BC_PREFIX,
    PAIR_SEG_PREFIX,
    CL3B_MACD_PREFIX,
    CMP_PREFIX,
)
PERFORMANCE_PRESET_THS_PREFIXES: tuple[str, ...] = (
    CMP_PREFIX,
    CL3B_MACD_PREFIX,
)

# ---------------------------------------------------------------------------
# AS 页：active_vol_then_nestedbc — 小周期
# ---------------------------------------------------------------------------
ACTIVE_VOL_NESTED_SHORT_FREQS: tuple[str, ...] = ("5m", "15m")
