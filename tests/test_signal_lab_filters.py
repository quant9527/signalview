"""策略分组选择器：分组纯函数测试。"""
from app_pages import _signal_lab_filters as f


def test_strategy_prefix():
    assert f.strategy_prefix("bc_xd4_macd") == "bc"
    assert f.strategy_prefix("cl2b_pair") == "cl2b"
    assert f.strategy_prefix("xianren") == "xianren"  # 无下划线自成一组
    assert f.strategy_prefix("") == ""


def test_group_strategies_groups_by_first_segment():
    strategies = [
        "bc_xd4_ma5ma10", "bc_xd4_macd",
        "cl2b_pair", "cl2b_surge", "cl2b_triangle",
        "xianren", "yd",
    ]
    assert f.group_strategies(strategies) == [
        ["bc_xd4_ma5ma10", "bc_xd4_macd"],
        ["cl2b_pair", "cl2b_surge", "cl2b_triangle"],
        ["xianren"],
        ["yd"],
    ]


def test_group_strategies_preserves_first_seen_order():
    strategies = ["cl2b_pair", "bc_xd4_macd", "cl2b_surge", "rebc_bo"]
    assert f.group_strategies(strategies) == [
        ["cl2b_pair", "cl2b_surge"],
        ["bc_xd4_macd"],
        ["rebc_bo"],
    ]


def test_group_strategies_empty():
    assert f.group_strategies([]) == []
