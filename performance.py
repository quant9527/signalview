import streamlit as st
from constants import EXCHANGE_AS, EXCHANGE_EM, EXCHANGE_THS, EXCHANGE_BINANCE
from performance_table import render_performance_signal_table
from signal_constants import SIGNAL_NAME_PREFIXES_PRELOAD

PERF_OTHER_GROUP = "other"


def _perf_group_key(group_id: str) -> str:
    return f"_perf_grp_{group_id}"


def _perf_nm_key(i: int) -> str:
    return f"_perf_nm_{i}"


def _make_perf_prefix_sync(gid: str, names: list[str], idx_map: dict[str, int]):
    """前缀勾选变化时，将组内所有子 signal 设为相同布尔值。"""

    def _cb():
        want = st.session_state.get(_perf_group_key(gid), False)
        for s in names:
            st.session_state[_perf_nm_key(idx_map[s])] = want

    return _cb


def _group_signals_by_prefix(
    signals: list[str],
    prefixes: tuple[str, ...],
) -> list[tuple[str, list[str]]]:
    """最长前缀优先匹配；返回 [(group_id, names), ...]，顺序与 prefixes 一致，最后为 other。"""
    pref_by_len = sorted(prefixes, key=len, reverse=True)
    buckets: dict[str, list[str]] = {p: [] for p in prefixes}
    other: list[str] = []
    for s in signals:
        raw = str(s)
        hit = next((p for p in pref_by_len if raw.startswith(p)), None)
        if hit is not None:
            buckets[hit].append(s)
        else:
            other.append(s)
    out: list[tuple[str, list[str]]] = [(p, buckets[p]) for p in prefixes if buckets[p]]
    if other:
        out.append((PERF_OTHER_GROUP, sorted(other)))
    return out


df_full = st.session_state.df.copy()

# Get main signal from session state (set by parent page)
main_signal = st.session_state.get("main_signal", "")

all_signals_list = sorted(df_full["signal_name"].dropna().unique().tolist())
signal_to_idx = {s: i for i, s in enumerate(all_signals_list)}
signal_groups = _group_signals_by_prefix(all_signals_list, SIGNAL_NAME_PREFIXES_PRELOAD)

# Default signals：main_signal 可为 str 或 str 元组（多前缀并集）
if main_signal:
    if isinstance(main_signal, (tuple, list)):
        prefixes = tuple(main_signal)
        default_set = {
            s for s in all_signals_list
            if any(str(s).startswith(p) for p in prefixes)
        }
    else:
        default_set = {s for s in all_signals_list if str(s).startswith(main_signal)}
else:
    default_set = set()

preset_key = (main_signal, tuple(all_signals_list))
if st.session_state.get("_perf_signal_preset_key") != preset_key:
    st.session_state["_perf_signal_preset_key"] = preset_key
    for i, s in enumerate(all_signals_list):
        st.session_state[_perf_nm_key(i)] = s in default_set

st.markdown("**Select signals**")
st.caption("前缀：一键全选/清空该组；子项：可单独勾选。仅部分子项选中时，前缀框为未勾选。")

_sel_a, _sel_b = st.columns(2)
with _sel_a:
    if st.button("全选", key="_perf_sig_btn_all"):
        for i in range(len(all_signals_list)):
            st.session_state[_perf_nm_key(i)] = True
        st.rerun()
with _sel_b:
    if st.button("清空", key="_perf_sig_btn_clear"):
        for i in range(len(all_signals_list)):
            st.session_state[_perf_nm_key(i)] = False
        st.rerun()

selected_signals: list[str] = []
_nc = 3
for gi, (gid, names) in enumerate(signal_groups):
    display_gid = gid if gid != PERF_OTHER_GROUP else "其他"
    all_on = (
        all(st.session_state.get(_perf_nm_key(signal_to_idx[s]), False) for s in names)
        if names
        else False
    )
    st.session_state[_perf_group_key(gid)] = all_on
    st.checkbox(
        f"前缀 `{display_gid}` · {len(names)} 个（勾选=全选本组，取消=全不选）",
        key=_perf_group_key(gid),
        on_change=_make_perf_prefix_sync(gid, names, signal_to_idx),
    )
    _scols = st.columns(_nc)
    for j, s in enumerate(names):
        with _scols[j % _nc]:
            if st.checkbox(s, key=_perf_nm_key(signal_to_idx[s])):
                selected_signals.append(s)
    if gi < len(signal_groups) - 1:
        st.divider()

# Filter data based on selected signals
if selected_signals:
    df = df_full[df_full['signal_name'].isin(selected_signals)].copy()
else:
    st.warning("Please select at least one signal")
    st.stop()

# Exchange 由入口页「功能」写入 session_state，避免与功能选择重复
exchange_option = st.session_state.get("exchange", EXCHANGE_AS)

# Filter by exchange if the column exists
if 'exchange' in df.columns:
    df = df[df['exchange'] == exchange_option].copy()

# Display signal and symbol counts after both selections
total_signals = len(selected_signals)
total_symbols = df['symbol'].nunique()
total_records = len(df)
st.info(f"📊 Selected signals: {total_signals} | Unique symbols: {total_symbols} | Total records: {total_records}")

if exchange_option == EXCHANGE_BINANCE:
    st.warning("Binance exchange not yet implemented")
    st.stop()

render_performance_signal_table(
    df,
    df_full,
    exchange=exchange_option,
    key_prefix="performance_main",
    show_summary_info=False,
    refresh_label="Refresh latest prices",
    na_checkbox_label="Include records without latest price",
    date_sort_label="Sort by signal date order",
    signal_date_sort_options=(("Descending", False), ("Ascending", True)),
    stop_on_empty_work=False,
    stop_on_empty_market=True,
)