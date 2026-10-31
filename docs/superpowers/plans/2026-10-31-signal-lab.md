# SIGNAL LAB 策略案例图库 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 signalview 新增 SIGNAL LAB 页面：飞书策略案例图库的卡片墙浏览体验（筛选/分页/详情弹窗/同策略左右翻动），案例数据来自仓库内静态 JSON，卡片缩略图与详情大图按案例的标的代码实时渲染 K 线。

**Architecture:** 数据层（`data/signal_lab_cases.json` + `_signal_lab_data.py` 纯函数）→ 展示层（`_signal_lab_thumbs.py` 自绘 SVG 缩略图、`_signal_lab_gallery.py` CCv2 卡片墙组件）→ 页面层（`signal_lab.py` 组装筛选/卡片墙/`@st.dialog` 详情）。详情 K 线复用 `app_pages/kline_charts.py` 现有 echarts 管线，K 线数据用 `flight_kline_client` 按 (exchange, freq) 分组批量拉取。

**Tech Stack:** Streamlit ≥1.59（`st.components.v2.component`、`@st.dialog`、`st.pills`）、pandas、pyarrow flight、pytest。缩略图不引入新依赖（手写 SVG 字符串）。

**设计文档:** `docs/superpowers/specs/2026-10-31-signal-lab-design.md`

---

## 背景知识（执行者必读）

- `flight_kline_client.fetch_kline_dataframe(tags, start_time_ms, end_time_ms, kline_aggregate="")` 一次 do_get 返回多标的混表；`build_kline_tags(symbols, exchange, kline_freq)` 生成 `{exchange}_{symbol}_{freq}` tags；派生频率（1w/1M）需传 `1d` tag + `kline_aggregate`。
- `app_pages/kline_charts.py`（本仓库惯用别名 `kc`）：`extract_symbol_data(df, sym_key, exchange)` → `(bars, meta)`；bars 列：`_x`(datetime)、`open/high/low/close`、`volume`；`to_echarts_ohlc/volume/ma/macd`、`build_symbol_candle_option(..., mark_date=)`、`build_chart_meta(labels, ohlc, ma_lines, signals)`、`build_echarts_html(chart_configs, metas)`。
- CCv2（`st.components.v2.component`）：模块级注册一次；JS 必须 `export default function(component)`，用 `setStateValue`/`setTriggerValue` 回传；**禁止 v1 API**（`components.v1.html`、`Streamlit.setComponentValue` 等）。state 键回调名 `on_<key>_change`。
- 页面在 `streamlit_app.py` 用 `st.Page` 注册到 `pages` 字典的分区列表。
- 运行测试：`cd /home/lei/repo/signalview && uv run pytest tests/<file> -v`

---

### Task 1: 数据抓取脚本与首份静态数据

**Files:**
- Create: `scripts/signal_lab_fetch.js`
- Create: `scripts/fetch_signal_lab.py`
- Create: `data/signal_lab_cases.json`（生成产物，入库）

- [ ] **Step 1: 写浏览器抓取 JS（`scripts/signal_lab_fetch.js`）**

```javascript
// scripts/signal_lab_fetch.js
// 用法：在已登录的飞书「策略库」标签页里执行（控制台或经 CDP evaluate_script）：
//   const cases = await signalLabFetch();
// 然后把 cases 保存为 JSON 文件交给 scripts/fetch_signal_lab.py 落盘。
const BASE = "M3Yvbt032aq8smsSi1BcrLisn9g";
const CASE_TABLE = "tblW6XBSpDRg3Q44";

async function gzipDecode(b64) {
  const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const stream = new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}

async function fetchTableBlob(tableId) {
  const url =
    `/space/api/v1/bitable/${BASE}/clientvars?tableID=${tableId}&viewID=` +
    `&recordLimit=200&ondemandLimit=200&needBase=true&viewLazyLoad=true` +
    `&ondemandVer=2&noMissCS=true&optimizationFlag=1&removeFmlExtra=true`;
  const d = (await fetch(url, { credentials: "include" }).then((r) => r.json())).data;
  return gzipDecode(d.table);
}

function cellText(value) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.map((v) => (v && v.text) || "").join("");
  if (typeof value === "object" && "text" in value) return String(value.text ?? "");
  return String(value);
}

// signal_name 是链接字段：解析其目标表，建 recordId -> 主键字段文本 的映射
async function linkedNameMap(fieldMap, fieldName) {
  const field = Object.values(fieldMap).find((f) => f.name === fieldName);
  if (!field) return {};
  const prop = field.property || {};
  const targetTable = prop.tableId || prop.targetTableId || prop.foreignTableId;
  if (!targetTable) return {};
  const t = await fetchTableBlob(targetTable);
  const pk = t.primaryKey;
  const map = {};
  for (const [rid, rec] of Object.entries(t.recordMap || {})) {
    const cell = rec[pk];
    map[rid] = cellText(cell && cell.value);
  }
  return map;
}

window.signalLabFetch = async function () {
  const table = await fetchTableBlob(CASE_TABLE);
  const fm = table.fieldMap || {};
  const find = (name) => Object.values(fm).find((f) => f.name === name);
  const byName = Object.fromEntries(Object.values(fm).map((f) => [f.name, f.id]));

  const signalOpts = {};
  const sf = find("signal");
  for (const o of (sf && sf.property && sf.property.options) || []) signalOpts[o.id] = o.name;
  const strategyNames = await linkedNameMap(fm, "signal_name");

  const out = [];
  for (const [rid, rec] of Object.entries(table.recordMap || {})) {
    const v = (id) => { const c = rec[id]; return c ? c.value : undefined; };
    const dateVal = v(byName["date"]);
    out.push({
      id: rid,
      name: cellText(v(byName["名称"])) || "未命名",
      date: typeof dateVal === "number" ? new Date(dateVal).toISOString().slice(0, 10) : cellText(dateVal),
      code: cellText(v(byName["symbol_id"])),
      signal: signalOpts[cellText(v(byName["signal"]))] || cellText(v(byName["signal"])) || "",
      strategy: strategyNames[cellText(v(byName["signal_name"]))] || "",
      info: cellText(v(byName["info"])),
      note: cellText(v(byName["注意点"])),
    });
  }
  return out;
};
```

- [ ] **Step 2: 写规范化落盘脚本（`scripts/fetch_signal_lab.py`）**

```python
"""规范化浏览器抓取的 SIGNAL LAB 案例数据并写入 data/signal_lab_cases.json。

用法：
    1. 在飞书策略库页面执行 scripts/signal_lab_fetch.js 的 signalLabFetch()
    2. 把返回数组保存为 JSON（如 /tmp/signal_lab_raw.json）
    3. uv run python scripts/fetch_signal_lab.py /tmp/signal_lab_raw.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "signal_lab_cases.json"


def normalize(raw: list[dict]) -> tuple[list[dict], int]:
    """丢弃缺 id/code 的记录；按 date 降序。返回 (cases, dropped)。"""
    cases = [c for c in raw if str(c.get("id", "")).strip() and str(c.get("code", "")).strip()]
    cases.sort(key=lambda c: (str(c.get("date") or ""), str(c.get("id") or "")), reverse=True)
    return cases, len(raw) - len(cases)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    cases, dropped = normalize(raw)
    payload = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(cases),
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写入 {OUT}: {len(cases)} 条（丢弃 {dropped} 条缺 id/code 的记录）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 3: 执行抓取**

在 Chrome（会话里已登录的飞书标签页，pageId=2）通过 CDP `evaluate_script` 执行
`scripts/signal_lab_fetch.js` 的全部函数定义 + `await signalLabFetch()`，
把返回数组写到 `/tmp/signal_lab_raw.json`（由工具侧保存），然后：

Run: `uv run python scripts/fetch_signal_lab.py /tmp/signal_lab_raw.json`
Expected: `写入 /home/lei/repo/signalview/data/signal_lab_cases.json: 300+ 条（丢弃 N 条…）`

- [ ] **Step 4: 校验数据质量**

```bash
uv run python -c "
import json
d = json.load(open('data/signal_lab_cases.json'))
cs = d['cases']
print('count', d['count'])
print('signals', sorted({c['signal'] for c in cs}))
print('strategies', len({c['strategy'] for c in cs}))
print('bad_date', sum(1 for c in cs if not c['date']))
print('sample', cs[0])
"
```

Expected: count ≥ 300；signals 出现 BUY/SELL 等；sample 含全部 8 个字段。

- [ ] **Step 5: Commit**

```bash
git add scripts/signal_lab_fetch.js scripts/fetch_signal_lab.py data/signal_lab_cases.json
git commit -m "feat: SIGNAL LAB 案例数据抓取脚本与首份静态数据"
```

---

### Task 2: 数据加载与筛选纯函数

**Files:**
- Create: `app_pages/_signal_lab_data.py`
- Test: `tests/test_signal_lab_data.py`

- [ ] **Step 1: 写失败测试（`tests/test_signal_lab_data.py`）**

```python
"""SIGNAL LAB 数据层纯函数测试。"""
import json
from pathlib import Path

import pytest

from app_pages import _signal_lab_data as d


@pytest.fixture
def cases() -> list[dict]:
    return [
        {"id": "r1", "name": "闽东电力", "date": "2025-07-27", "code": "as:000993:1h",
         "signal": "BUY", "strategy": "bc_xd4", "info": "a", "note": ""},
        {"id": "r2", "name": "创业板", "date": "2026-01-01", "code": "asindex:sz399006:2h",
         "signal": "SELL", "strategy": "bc_xd4", "info": "", "note": "n"},
        {"id": "r3", "name": "沐曦股份", "date": "2025-10-19", "code": "as:688802:2h",
         "signal": "BUY", "strategy": "cl2b", "info": "i", "note": ""},
    ]


def test_parse_code_valid():
    assert d.parse_code("as:000993:1h") == ("as", "000993", "1h")
    assert d.parse_code("asindex:sz399006:2h") == ("asindex", "sz399006", "2h")


def test_parse_code_invalid():
    assert d.parse_code("as:000993") is None
    assert d.parse_code("::1h") is None
    assert d.parse_code("") is None


def test_filter_cases_all(cases):
    out = d.filter_cases(cases)
    # date 降序
    assert [c["id"] for c in out] == ["r2", "r3", "r1"]


def test_filter_cases_by_strategy_and_signal(cases):
    assert [c["id"] for c in d.filter_cases(cases, strategy="cl2b")] == ["r3"]
    assert [c["id"] for c in d.filter_cases(cases, signal="BUY")] == ["r3", "r1"]
    assert d.filter_cases(cases, keyword="沐曦")[0]["id"] == "r3"
    assert d.filter_cases(cases, keyword="沐曦", signal="SELL") == []


def test_paginate(cases):
    page_cases, page_no, total = d.paginate(cases, page=1, per_page=2)
    assert page_no == 1 and total == 2 and len(page_cases) == 2
    page_cases, page_no, total = d.paginate(cases, page=99, per_page=2)
    assert page_no == 2 and [c["id"] for c in page_cases] == ["r1"]


def test_strategy_and_signal_options(cases):
    assert d.strategy_options(cases) == ["bc_xd4", "cl2b"]
    assert d.signal_options(cases) == ["BUY", "SELL"]


def test_load_cases_from_file(tmp_path: Path):
    p = tmp_path / "cases.json"
    p.write_text(json.dumps({"count": 1, "cases": [
        {"id": "x", "name": "n", "date": "2025-01-01", "code": "as:000001:1d",
         "signal": "BUY", "strategy": "s", "info": "", "note": ""},
        {"id": "bad"},  # 缺必填键，被跳过
    ]}), encoding="utf-8")
    out = d.load_cases(p)
    assert len(out) == 1 and out[0]["id"] == "x"


def test_load_cases_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        d.load_cases(tmp_path / "nope.json")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_signal_lab_data.py -v`
Expected: FAIL（`ModuleNotFoundError: app_pages._signal_lab_data`）

- [ ] **Step 3: 实现（`app_pages/_signal_lab_data.py`）**

```python
"""SIGNAL LAB 案例数据：加载、校验、筛选、分页（纯函数，便于测试）。"""
from __future__ import annotations

import json
import math
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "signal_lab_cases.json"

REQUIRED_KEYS = ("id", "name", "date", "code", "signal", "strategy")
_CASE_KEYS = ("id", "name", "date", "code", "signal", "strategy", "info", "note")


def load_cases(path: Path = DATA_PATH) -> list[dict]:
    """读取并校验案例 JSON。缺失抛 FileNotFoundError，格式错抛 ValueError。

    缺少任一必填键的记录被跳过（不崩溃）。
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(cases, list):
        raise ValueError("signal_lab_cases.json 缺少 cases 列表")
    out = []
    for c in cases:
        if isinstance(c, dict) and all(k in c for k in REQUIRED_KEYS):
            out.append({k: c.get(k, "") for k in _CASE_KEYS})
    return out


@st.cache_data(ttl=600, max_entries=4)
def get_cases() -> list[dict]:
    """页面入口：读取仓库静态数据（短缓存，改 JSON 后最多 10 分钟生效）。"""
    return load_cases()


def parse_code(code: str) -> tuple[str, str, str] | None:
    """`as:000993:1h` -> `('as', '000993', '1h')`；不合法返回 None。"""
    parts = [p.strip() for p in str(code).split(":")]
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def filter_cases(
    cases: list[dict],
    strategy: str = "全部策略",
    keyword: str = "",
    signal: str = "全部",
) -> list[dict]:
    """按策略/名称关键词/信号类型过滤，date 降序。"""
    kw = keyword.strip().lower()
    out = []
    for c in cases:
        if strategy != "全部策略" and c["strategy"] != strategy:
            continue
        if signal != "全部" and c["signal"] != signal:
            continue
        if kw and kw not in str(c["name"]).lower():
            continue
        out.append(c)
    return sorted(out, key=lambda c: (str(c["date"]), str(c["id"])), reverse=True)


def paginate(
    cases: list[dict], page: int, per_page: int = 28
) -> tuple[list[dict], int, int]:
    """返回 (当前页案例, 钳制后的页码, 总页数)。"""
    total_pages = max(1, math.ceil(len(cases) / per_page))
    page = min(max(1, int(page)), total_pages)
    start = (page - 1) * per_page
    return cases[start:start + per_page], page, total_pages


def strategy_options(cases: list[dict]) -> list[str]:
    return sorted({str(c["strategy"]) for c in cases if c["strategy"]})


def signal_options(cases: list[dict]) -> list[str]:
    return sorted({str(c["signal"]) for c in cases if c["signal"]})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_signal_lab_data.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app_pages/_signal_lab_data.py tests/test_signal_lab_data.py
git commit -m "feat: SIGNAL LAB 数据加载与筛选纯函数"
```

---

### Task 3: SVG 缩略图模块

**Files:**
- Create: `app_pages/_signal_lab_thumbs.py`
- Test: `tests/test_signal_lab_thumbs.py`

- [ ] **Step 1: 写失败测试（`tests/test_signal_lab_thumbs.py`）**

```python
"""SIGNAL LAB 缩略图：窗口切片与 SVG 渲染测试（合成数据，不打网络）。"""
import pandas as pd
import pytest

from app_pages import _signal_lab_thumbs as t


@pytest.fixture
def bars() -> pd.DataFrame:
    """80 根合成日 K：_x + OHLC + volume。"""
    rows = []
    base = pd.Timestamp("2025-01-01")
    for i in range(80):
        o = 10.0 + i * 0.1
        rows.append({
            "_x": base + pd.Timedelta(days=i),
            "open": o, "high": o + 0.5, "low": o - 0.4, "close": o + 0.2,
            "volume": 1000.0 + i,
        })
    return pd.DataFrame(rows)


def test_slice_window_anchors_case_date(bars):
    w = t.slice_window(bars, "2025-03-01")
    # 案例日在窗口内，且长度不超过 before+after+1
    assert len(w) <= t.WINDOW_BEFORE + t.WINDOW_AFTER + 1
    assert w["_x"].min() <= pd.Timestamp("2025-03-01") <= w["_x"].max()


def test_slice_window_edges(bars):
    # 案例日期远超数据范围时取最近一根，不抛异常
    w = t.slice_window(bars, "2030-01-01")
    assert len(w) == t.WINDOW_AFTER + 1


def test_slice_window_empty():
    assert t.slice_window(pd.DataFrame(), "2025-01-01") is None


def test_render_candle_svg_contains_candles(bars):
    svg = t.render_candle_svg(bars, "2025-03-01")
    assert svg is not None and svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'stroke-dasharray' in svg  # 案例日标记线存在


def test_render_candle_svg_empty():
    assert t.render_candle_svg(pd.DataFrame(), "2025-01-01") is None


def test_placeholder_svg():
    svg = t.placeholder_svg()
    assert svg.startswith("<svg") and "暂无" in svg
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_signal_lab_thumbs.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现（`app_pages/_signal_lab_thumbs.py`）**

```python
"""SIGNAL LAB 卡片缩略图：自绘 SVG 迷你蜡烛图（含成交量柱 + 案例日标记）。

不引入新依赖；K 线数据按 (exchange, freq) 分组经 flight 批量拉取。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_pages._signal_lab_data import parse_code
from app_pages.kline_charts import extract_symbol_data
from flight_kline_client import build_kline_tags, fetch_kline_dataframe

WINDOW_BEFORE = 60
WINDOW_AFTER = 20

# freq -> 回看日历天数（保证能取到 WINDOW_BEFORE + WINDOW_AFTER 根）
FREQ_LOOKBACK_DAYS = {
    "15m": 5, "30m": 10, "1h": 30, "2h": 60, "4h": 120,
    "1d": 400, "1w": 2800, "1M": 6000,
}
_DEFAULT_LOOKBACK_DAYS = 400
# 派生频率：服务端不直接入库，取 1d 数据由服务端聚合
DERIVED_FREQS = {"1w": "1d", "1M": "1d"}

_UP = "#26a69a"
_DOWN = "#ef5350"
_MARK = "#f59e0b"


def slice_window(
    bars: pd.DataFrame,
    case_date: str,
    before: int = WINDOW_BEFORE,
    after: int = WINDOW_AFTER,
) -> pd.DataFrame | None:
    """取案例日期前 before 根 + 后 after 根；案例日无精确匹配时锚定最近一根。"""
    if bars is None or bars.empty:
        return None
    target = pd.Timestamp(case_date)
    idx = (bars["_x"] - target).abs().idxmin()
    pos = bars.index.get_loc(idx)
    start = max(0, pos - before)
    end = min(len(bars), pos + after + 1)
    return bars.iloc[start:end]


def fetch_case_bars(code_dates: dict[str, str]) -> dict[str, pd.DataFrame]:
    """批量拉取 {code: 案例日期} 的 K 线；返回 {code: bars}，失败的不出现。"""
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for code, d in code_dates.items():
        parsed = parse_code(code)
        if parsed:
            ex, sym, freq = parsed
            groups.setdefault((ex, freq), []).append((sym, d))

    out: dict[str, pd.DataFrame] = {}
    for (ex, freq), items in groups.items():
        syms = [s for s, _ in items]
        dates = [pd.Timestamp(d) for _, d in items]
        lookback = FREQ_LOOKBACK_DAYS.get(freq, _DEFAULT_LOOKBACK_DAYS)
        start_ms = int((min(dates) - pd.Timedelta(days=lookback)).value // 1e6)
        end_ms = int((max(dates) + pd.Timedelta(days=30)).value // 1e6)
        tag_freq = DERIVED_FREQS.get(freq, freq)
        try:
            tags = build_kline_tags(syms, ex, kline_freq=tag_freq)
            df = fetch_kline_dataframe(tags, start_ms, end_ms, kline_aggregate=DERIVED_FREQS.get(freq, ""))
        except Exception:
            continue
        if df is None:
            continue
        for sym, d in items:
            parsed = extract_symbol_data(df, sym, exchange=ex)
            if parsed is not None:
                out[f"{ex}:{sym}:{freq}"] = parsed[0]
    return out


def render_candle_svg(
    bars: pd.DataFrame,
    case_date: str,
    width: int = 264,
    height: int = 148,
    vol_ratio: float = 0.22,
) -> str | None:
    """把窗口 K 线渲染成迷你蜡烛 SVG（成交量柱 + 案例日虚线标记）。"""
    if bars is None or len(bars) == 0:
        return None
    n = len(bars)
    pad_l, pad_r, pad_t = 4.0, 4.0, 6.0
    plot_h = height - pad_t - 4.0
    vol_h = plot_h * vol_ratio
    k_h = plot_h - vol_h - 4.0
    step = (width - pad_l - pad_r) / n
    body_w = max(1.5, step * 0.66)
    hi = float(bars["high"].max())
    lo = float(bars["low"].min())
    span = (hi - lo) or 1.0
    has_vol = "volume" in bars.columns and bars["volume"].notna().any()
    vmax = float(bars["volume"].max()) if has_vol else 0.0

    target = pd.Timestamp(case_date)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">']
    mark_x: float | None = None
    for i, (_, b) in enumerate(bars.iterrows()):
        cx = pad_l + step * (i + 0.5)
        o, c = float(b["open"]), float(b["close"])
        up = c >= o
        color = _UP if up else _DOWN
        y_wick_top = pad_t + (hi - float(b["high"])) / span * k_h
        y_wick_bot = pad_t + (hi - float(b["low"])) / span * k_h
        y_top = pad_t + (hi - max(o, c)) / span * k_h
        bh = max(1.0, abs(c - o) / span * k_h)
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y_wick_top:.1f}" x2="{cx:.1f}" y2="{y_wick_bot:.1f}" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        parts.append(
            f'<rect x="{cx - body_w / 2:.1f}" y="{y_top:.1f}" width="{body_w:.1f}" '
            f'height="{bh:.1f}" fill="{color}"/>'
        )
        if has_vol:
            vh = (float(b.get("volume", 0.0) or 0.0) / vmax) * vol_h if vmax else 0.0
            y_vol = pad_t + k_h + 4.0 + (vol_h - vh)
            parts.append(
                f'<rect x="{cx - body_w / 2:.1f}" y="{y_vol:.1f}" width="{body_w:.1f}" '
                f'height="{max(0.5, vh):.1f}" fill="{color}" opacity="0.4"/>'
            )
        if mark_x is None and abs((b["_x"] - target).total_seconds()) < 86400 * 1.5:
            mark_x = cx
    if mark_x is not None:
        parts.append(
            f'<line x1="{mark_x:.1f}" y1="{pad_t:.1f}" x2="{mark_x:.1f}" '
            f'y2="{pad_t + k_h + 4.0 + vol_h:.1f}" stroke="{_MARK}" stroke-width="1" stroke-dasharray="2,2"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def placeholder_svg(width: int = 264, height: int = 148) -> str:
    """K 线不可用时的占位图。"""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none"><text x="50%" y="50%" text-anchor="middle" '
        f'dominant-baseline="middle" fill="#98a2b3" font-size="13">暂无 K 线数据</text></svg>'
    )


@st.cache_data(ttl=86400, max_entries=64, show_spinner=False)
def thumbs_for_page(code_dates: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """为一页案例生成缩略图；key 为 `code|date`，value 为 SVG 字符串。"""
    code_date_map = {code: d for code, d in code_dates}
    bars_map = fetch_case_bars(code_date_map)
    out: dict[str, str] = {}
    for code, d in code_date_map:
        bars = bars_map.get(code)
        svg = render_candle_svg(slice_window(bars, d), d) if bars is not None else None
        out[f"{code}|{d}"] = svg or placeholder_svg()
    return out
```

注意：`fetch_case_bars` 返回的 dict key 是 `{ex}:{sym}:{freq}`（即原始 code 重新拼装），
与传入 code 一致的前提是 code 本身就是三段式——`parse_code` 已保证。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_signal_lab_thumbs.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app_pages/_signal_lab_thumbs.py tests/test_signal_lab_thumbs.py
git commit -m "feat: SIGNAL LAB SVG 蜡烛图缩略图模块"
```

---

### Task 4: CCv2 卡片墙组件

**Files:**
- Create: `app_pages/_signal_lab_gallery.py`
- Test: `tests/test_signal_lab_gallery.py`

- [ ] **Step 1: 写失败测试（`tests/test_signal_lab_gallery.py`）**

```python
"""卡片墙组件：payload 构造纯函数测试。"""
from app_pages import _signal_lab_gallery as g


def test_signal_class_known():
    assert g.signal_class("BUY") == "buy"
    assert g.signal_class("SELL") == "sell"
    assert g.signal_class("IGNORE_BUY") == "ignore"
    assert g.signal_class("NOT_BUY") == "notbuy"
    assert g.signal_class("LONG / BUY") == "long"


def test_signal_class_fallback():
    assert g.signal_class("UNKNOWN_X").startswith("sig-")


def test_build_cards_payload():
    thumbs = {"as:000993:1h|2025-07-27": "<svg>t</svg>"}
    cases = [{"id": "r1", "name": "闽东电力", "date": "2025-07-27",
              "code": "as:000993:1h", "signal": "BUY"}]
    cards = g.build_cards_payload(cases, thumbs)
    assert cards[0]["id"] == "r1"
    assert cards[0]["name"] == "闽东电力"
    assert cards[0]["dateLabel"] == "2025.07.27"
    assert cards[0]["signal"] == "BUY"
    assert cards[0]["thumb"] == "<svg>t</svg>"


def test_build_cards_payload_missing_thumb_uses_placeholder():
    cards = g.build_cards_payload(
        [{"id": "r1", "name": "n", "date": "2025-01-01", "code": "c", "signal": "SELL"}], {}
    )
    assert cards[0]["thumb"].startswith("<svg")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_signal_lab_gallery.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现（`app_pages/_signal_lab_gallery.py`）**

```python
"""SIGNAL LAB 卡片墙 CCv2 组件：整面网格 1 个 widget，点击卡片回传 case id。"""
from __future__ import annotations

from collections.abc import Callable

import streamlit as st

_SIGNAL_CLASS = {
    "BUY": "buy",
    "SELL": "sell",
    "IGNORE_BUY": "ignore",
    "NOT_BUY": "notbuy",
    "LONG / BUY": "long",
}


def signal_class(signal: str) -> str:
    """信号类型 -> CSS 修饰类；未知类型给中性色。"""
    cls = _SIGNAL_CLASS.get(str(signal).strip())
    if cls:
        return cls
    return "sig-" + "".join(ch if ch.isalnum() else "-" for ch in str(signal).lower())[:20]


def build_cards_payload(cases: list[dict], thumbs: dict[str, str]) -> list[dict]:
    """把当前页案例 + 缩略图组装成组件 data；纯函数。"""
    cards = []
    for c in cases:
        key = f"{c['code']}|{c['date']}"
        cards.append({
            "id": str(c["id"]),
            "name": str(c["name"]),
            "dateLabel": str(c["date"]).replace("-", "."),
            "signal": str(c["signal"]),
            "signalClass": signal_class(str(c["signal"])),
            "thumb": thumbs.get(key) or "<svg xmlns='http://www.w3.org/2000/svg'/>",
        })
    return cards


_HTML = "<div id=\"root\"></div>"

_CSS = """
#root{font-family:var(--st-font, sans-serif);color:var(--st-text-color)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.card{position:relative;border-radius:12px;overflow:hidden;cursor:pointer;
  background:var(--st-secondary-background-color,#fff);
  border:1px solid var(--st-border-color,rgba(0,0,0,.08));
  transition:box-shadow .18s ease,transform .18s ease}
.card:hover{box-shadow:0 8px 24px rgba(0,0,0,.12);transform:translateY(-2px)}
.thumb{aspect-ratio:16/9;background:var(--st-secondary-background-color,#f5f5f5)}
.thumb svg{width:100%;height:100%;display:block}
.badge{position:absolute;top:10px;left:10px;padding:2px 10px;border-radius:999px;
  font-size:11px;font-weight:600;letter-spacing:.04em;color:#fff;background:#64748b}
.badge-buy{background:#5f8d78}.badge-sell{background:#c0504d}
.badge-ignore{background:#8a8f98}.badge-notbuy{background:#4b5563}
.badge-long{background:#4a7bb5}
.hover{position:absolute;inset:0 0 44px 0;display:flex;align-items:center;justify-content:center;
  background:rgba(15,23,42,.45);opacity:0;transition:opacity .18s ease}
.card:hover .hover{opacity:1}
.hover span{color:#fff;font-size:13px;border:1px solid rgba(255,255,255,.7);
  border-radius:999px;padding:4px 14px}
.meta{padding:10px 12px 12px}
.name{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.date{font-size:12px;opacity:.6;margin-top:2px}
.pager{display:flex;align-items:center;justify-content:center;gap:14px;margin-top:18px;
  font-size:13px;opacity:.85}
.pg{border:1px solid var(--st-border-color,rgba(0,0,0,.15));background:transparent;
  color:inherit;border-radius:8px;padding:3px 12px;cursor:pointer;font-size:14px}
.pg:disabled{opacity:.35;cursor:default}
.pg:not(:disabled):hover{background:var(--st-secondary-background-color,#f0f0f0)}
"""

_JS = """
export default function (component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component;
  const root = parentElement.querySelector("#root");
  if (!root) return;
  const cards = (data && data.cards) || [];
  const page = (data && data.page) || 1;
  const total = (data && data.totalPages) || 1;
  const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]
  ));
  root.innerHTML = `
    <div class="grid">
      ${cards.map((c) => `
        <div class="card" data-id="${esc(c.id)}">
          <div class="thumb">${c.thumb || ""}</div>
          <span class="badge badge-${esc(c.signalClass)}">${esc(c.signal)}</span>
          <div class="hover"><span>查看详情</span></div>
          <div class="meta">
            <div class="name">${esc(c.name)}</div>
            <div class="date">${esc(c.dateLabel)}</div>
          </div>
        </div>`).join("")}
    </div>
    <div class="pager">
      <button class="pg" type="button" data-p="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹</button>
      <span>第 ${page} 页 · 共 ${total} 页</span>
      <button class="pg" type="button" data-p="${page + 1}" ${page >= total ? "disabled" : ""}>›</button>
    </div>`;
  root.querySelectorAll(".card").forEach((el) => {
    el.addEventListener("click", () => setTriggerValue("selected", el.dataset.id));
  });
  root.querySelectorAll(".pg").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = parseInt(btn.dataset.p, 10);
      if (p >= 1 && p <= total) setStateValue("page", p);
    });
  });
}
"""

# 模块级注册一次
_GALLERY = st.components.v2.component(
    "signal_lab_gallery", html=_HTML, css=_CSS, js=_JS
)


def render_gallery(
    cards: list[dict],
    page: int,
    total_pages: int,
    *,
    key: str = "sl_gallery",
) -> object:
    """渲染卡片墙；返回组件 result（.selected 为本次点击的 case id 触发值）。"""
    return _GALLERY(
        key=key,
        data={"cards": cards, "page": page, "totalPages": total_pages},
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_signal_lab_gallery.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app_pages/_signal_lab_gallery.py tests/test_signal_lab_gallery.py
git commit -m "feat: SIGNAL LAB CCv2 卡片墙组件"
```

---

### Task 5: 详情弹窗与主页面

**Files:**
- Create: `app_pages/signal_lab.py`
- Modify: `streamlit_app.py`（import + 注册到 `pages` 字典新分区「案例库」）

前置确认（实现时先看，不改）：`streamlit_app.py` 是否已在入口调用 `st.set_page_config`；
若已调用，`signal_lab.py` 内不再调用；若没有，在 `page_signal_lab()` 首行调用
`st.set_page_config(layout="wide", page_title="SIGNAL LAB", page_icon="🔬")`（与 `kline_fullscreen.py:329` 同模式）。

- [ ] **Step 1: 实现 `app_pages/signal_lab.py`**

```python
"""SIGNAL LAB — 策略案例图库。

数据来自 data/signal_lab_cases.json（飞书策略库抓取），
卡片缩略图与详情大图按案例 symbol_id 实时渲染 K 线。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_pages import _signal_lab_data as d
from app_pages import _signal_lab_gallery as g
from app_pages import _signal_lab_thumbs as t
from app_pages import kline_charts as kc
from flight_kline_client import build_kline_tags, fetch_kline_dataframe

PER_PAGE = 28
_GALLERY_KEY = "sl_gallery"


def _case_chart_html(case: dict, height: int = 520) -> str | None:
    """详情弹窗的完整 echarts K 线 HTML；拉不到数据返回 None。"""
    parsed = d.parse_code(case["code"])
    if parsed is None:
        return None
    ex, sym, freq = parsed
    lookback = t.FREQ_LOOKBACK_DAYS.get(freq, t._DEFAULT_LOOKBACK_DAYS)
    start = pd.Timestamp(case["date"]) - pd.Timedelta(days=lookback)
    end = pd.Timestamp(case["date"]) + pd.Timedelta(days=30)
    tags = build_kline_tags([sym], ex, kline_freq=t.DERIVED_FREQS.get(freq, freq))
    try:
        df = fetch_kline_dataframe(tags, int(start.value // 1e6), int(end.value // 1e6),
                                   kline_aggregate=t.DERIVED_FREQS.get(freq, ""))
    except Exception:
        return None
    prepared = kc.extract_symbol_data(df, sym, exchange=ex) if df is not None else None
    if prepared is None:
        return None
    bars, meta = prepared
    window = t.slice_window(bars, case["date"], before=150, after=40)
    labels = kc.date_labels(window["_x"], freq=freq)
    ohlc = kc.to_echarts_ohlc(window)
    vol = kc.to_echarts_volume(window)
    ma_lines = kc.to_echarts_ma(window, meta["ma_cols"])
    macd = kc.to_echarts_macd(window, meta["macd"])
    has_vol = bool(meta["has_volume"] and window["volume"].notna().any())
    option = kc.build_symbol_candle_option(
        title=f"{case['name']} · {case['code']}",
        labels=labels, ohlc=ohlc, volume=vol, ma_lines=ma_lines, macd=macd,
        has_volume=has_vol, signals=None, height=height, mark_date=case["date"],
    )
    charts = [{"id": "ch_case", "height": height, "option": option}]
    metas = {"ch_case": kc.build_chart_meta(labels, ohlc, ma_lines, None)}
    return kc.build_echarts_html(charts, metas)


@st.dialog("案例详情", width="large")
def _show_case_dialog(cases_lookup: dict[str, dict]) -> None:
    """详情弹窗；底部在 sl_case_ids 内循环翻动。"""
    cur_id = st.session_state.get("sl_case_id", "")
    ids = st.session_state.get("sl_case_ids", [])
    case = cases_lookup.get(cur_id)
    if case is None:
        st.warning("案例不存在，可能数据已更新。")
        return
    pos = ids.index(cur_id) if cur_id in ids else 0

    left, right = st.columns([3, 2])
    with left:
        html = _case_chart_html(case)
        if html:
            # 与 kline_fullscreen 一致：内联 echarts HTML 用 components.html 渲染
            import streamlit.components.v1 as components_v1
            components_v1.html(html, height=540)
        else:
            st.info("K 线数据暂不可用（标的代码无法解析或数据源无此合约）。")
    with right:
        st.markdown(f"#### {case['name']}")
        rows = [
            ("日期", case["date"].replace("-", ".")),
            ("标的代码", f"`{case['code']}`"),
            ("策略", case["strategy"] or "—"),
            ("信号", case["signal"]),
            ("信息", case["info"] or "—"),
            ("注意点", case["note"] or "—"),
        ]
        for label, value in rows:
            st.markdown(f"**{label}**")
            st.markdown(str(value))

    prev_b, next_b, _ = st.columns([1, 1, 4])
    if prev_b.button("← 上一个", key="sl_prev") and ids:
        st.session_state["sl_case_id"] = ids[(pos - 1) % len(ids)]
        st.rerun()
    if next_b.button("下一个 →", key="sl_next") and ids:
        st.session_state["sl_case_id"] = ids[(pos + 1) % len(ids)]
        st.rerun()


def _topbar(cases: list[dict]) -> None:
    n_cases = len(cases)
    n_signals = len(d.signal_options(cases))
    st.markdown(
        f"""
        <div style="padding:.25rem 0 .5rem 0;display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap">
          <span style="font-size:1.6rem;font-weight:700;letter-spacing:.35em">SIGNAL LAB</span>
          <span style="font-size:.85rem;opacity:.65">策略案例图库</span>
          <span style="font-size:.8rem;opacity:.5;margin-left:auto">{n_cases} 个案例 · {n_signals} 类信号</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_signal_lab() -> None:
    try:
        cases = d.get_cases()
    except (FileNotFoundError, ValueError) as e:
        st.error(f"案例数据不可用：{e}。请运行 scripts/fetch_signal_lab.py 重新生成 data/signal_lab_cases.json。")
        return
    if not cases:
        st.error("案例数据为空。")
        return

    _topbar(cases)

    c_strat, c_kw = st.columns([1, 2])
    with c_strat:
        strategy = st.selectbox(
            "策略", ["全部策略"] + d.strategy_options(cases),
            key="sl_strategy", label_visibility="collapsed",
        )
    with c_kw:
        keyword = st.text_input("搜索案例名称", key="sl_kw",
                                placeholder="搜索案例名称…", label_visibility="collapsed")
    signal = st.pills("信号", ["全部"] + d.signal_options(cases), key="sl_signal")

    filtered = d.filter_cases(cases, strategy=strategy, keyword=keyword, signal=signal)
    cur_page = 1
    state = st.session_state.get(_GALLERY_KEY)
    if isinstance(state, dict) and isinstance(state.get("page"), int):
        cur_page = state["page"]
    page_cases, page_no, total_pages = d.paginate(filtered, cur_page, PER_PAGE)

    thumbs = t.thumbs_for_page(tuple((c["code"], c["date"]) for c in page_cases))
    cards = g.build_cards_payload(page_cases, thumbs)
    result = g.render_gallery(cards, page_no, total_pages, key=_GALLERY_KEY)

    selected = getattr(result, "selected", None)
    if selected:
        by_id = {c["id"]: c for c in filtered}
        hit = by_id.get(selected)
        if hit is not None:
            st.session_state["sl_case_id"] = selected
            st.session_state["sl_case_ids"] = [
                c["id"] for c in filtered if c["strategy"] == hit["strategy"]
            ]

    if st.session_state.get("sl_case_id"):
        _show_case_dialog({c["id"]: c for c in cases})

    st.markdown(
        f"<div style='text-align:center;opacity:.5;font-size:.8rem;padding:1.5rem 0'>"
        f"SIGNAL LAB © 2026 策略案例图库 · 共 {len(cases)} 个案例</div>",
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: 注册页面（`streamlit_app.py`）**

在 import 区追加：

```python
from app_pages.signal_lab import page_signal_lab
```

在 `pages` 字典「K线」分区之前插入新分区：

```python
    "案例库": [
        st.Page(page_signal_lab, title="SIGNAL LAB", icon="🔬", url_path="signal_lab"),
    ],
```

- [ ] **Step 3: 冒烟验证页面可运行**

```bash
uv run python -c "
from app_pages.signal_lab import page_signal_lab, _case_chart_html
from app_pages import _signal_lab_data as d
cases = d.get_cases()
print('cases:', len(cases))
print('filtered BUY:', len(d.filter_cases(cases, signal='BUY')))
"
```

Expected: 打印案例数（≥300）与 BUY 数量，无异常。

- [ ] **Step 4: Commit**

```bash
git add app_pages/signal_lab.py streamlit_app.py
git commit -m "feat: SIGNAL LAB 页面（筛选/卡片墙/详情弹窗/同策略翻动）"
```

---

### Task 6: 端到端验收

**Files:** 无新增（验证 + 视觉微调可能触及 `app_pages/_signal_lab_gallery.py` 的 CSS）

- [ ] **Step 1: 全量测试**

Run: `uv run pytest tests/ -v`
Expected: 全部 PASS（含既有测试）

- [ ] **Step 2: 启动应用**

检查是否已有 Streamlit 在 8501 端口（`lsof -nP -iTCP:8501 -sTCP:LISTEN`）；
没有则 `uv run streamlit run streamlit_app.py --server.port 8501`（后台运行）。

- [ ] **Step 3: 浏览器验收**

用 Chrome（本会话已有 CDP 连接）打开 `http://localhost:8501/signal_lab`，逐项检查：

1. 顶栏显示案例总数与信号类数（与 JSON 一致）
2. 策略下拉 / 搜索 / 信号 pills 过滤生效且组合正确
3. 卡片墙渲染：缩略图为真蜡烛图（红绿蜡烛 + 成交量 + 橙色案例日虚线），徽章颜色区分
4. hover 出现「查看详情」浮层；分页条翻页正常、缩略图随之更新
5. 点击卡片打开详情弹窗：左侧 echarts K 线 + 案例日 markDate，右侧字段齐全
6. 弹窗内「上一个/下一个」在同一策略案例间循环翻动，图表随之切换
7. 「暂无图片」类案例（K 线拉不到）显示占位图，不白屏

发现问题（布局/交互/性能）就地修复后重跑 Step 1。

- [ ] **Step 4: Commit（如有修复）**

```bash
git add -A app_pages/ tests/
git commit -m "fix: SIGNAL LAB 验收问题修复"
```

---

## Self-Review 结论

- 规格覆盖：数据契约→Task 1/2；页面结构五区块→Task 5；缩略图→Task 3；卡片墙/分页→Task 4；详情弹窗/同策略翻动→Task 5；错误处理→Task 2（load_cases）/Task 3（placeholder）/Task 5（弹窗 warning）；测试→Task 2/3/4 + Task 6。无缺口。
- 类型一致性：`parse_code/filter_cases/paginate`（Task 2）在 Task 3/5 中的调用签名一致；`thumbs_for_page` 输入 `tuple[tuple[str,str],...]`、key `code|date` 与 Task 4 `build_cards_payload` 的 key 构造一致；`slice_window`/`FREQ_LOOKBACK_DAYS`/`DERIVED_FREQS` 在 Task 5 复用名一致。
- 已知取舍：详情 K 线渲染沿用仓库现有 `components.v1.html`（与 `kline_fullscreen` 一致；CCv2 仅用于新卡片墙组件）；`st.pills` 单选模式为默认行为。
