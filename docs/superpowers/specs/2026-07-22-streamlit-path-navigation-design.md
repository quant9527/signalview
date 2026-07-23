# Streamlit path-based multipage 改造设计

- **日期**：2026-07-22
- **范围**：`signalview` Streamlit 入口的导航结构、跨页状态、K 线页 URL 协议、版本升级。
- **状态**：设计稿，待用户最终评审。

## 背景与现状

`signalview` 是基于 Streamlit 的信号可视化面板（`http://host:8501`），入口 `streamlit_app.py:1-60` 已使用
`st.navigation(pages, position="top")` 注册 8 个分组、共 21 个页面，K 线页显式 `url_path="kline"`，其余走文件
名 hash 推断。Streamlit 版本：项目 `uv.lock` 锁 1.55.0，全局 `/home/lei/.local/bin/streamlit` 1.59.2（CLI 与运行时
不一致）。

子代理梳理（`agent-aa35324cb8bcfca01` / `agent-abe682e0b6c6e306c`）识别了以下问题：

1. `views/review_*.py`（today / em / key）三个页面用 `exec(open('search_signals.py').read())` 把控制权交给
   `search_signals.py`，依赖一组 `session_state['_is_review_mode' / '_auto_select_recent_2_days' /
   '_preset_exchange' / '_preset_signals']` 注入预设；任一文件被改名 exec 静默失效。
2. `views/performance.py` 写 `session_state.main_signal / exchange / df / _perf_*`，再 `exec(open('../performance.py').read())` 顶层 `performance.py`；同样隐式契约 + 紧耦合。
3. 跨页 `session_state['selected_signals']` / `['_is_binance_page']` 被多个页读取但**无任何写入方**（历史 sidebar 残留）。
4. K 线页没有"全屏"入口（worktree 草稿 `kline_fullscreen.py` 在 `.claude/worktrees/` 存在但未合入主线）。
5. `views/` 与 skill 模板（`app_pages/`）不一致，page 文件夹命名与 docs/AGENTS.md 描述未同步。
6. 全局 CLI 与 venv streamlit 版本漂移。

源码与子代理交叉核对的硬约束：

- `st.Page` `url_path` 不含 `/`、不含子目录；非 `default` 页 `url_path=""` 抛 `StreamlitAPIException`；`default=True` 时 `url_path` 属性强制返回 `""`。
- `st.navigation` 内部去重键 = `calc_md5(self._url_path)`；当前 23 个 page（不含新增 kline_fullscreen）0 冲突。
- `st.Page` 在裸 Python（无 ScriptRunContext）init 早 return；单元测试需通过 `monkeypatch` stub streamlit。
- `st.Page(callable, url_path=...)` 要求 callable 模块级 `def`，**不能**是 lambda 闭包（lambda 全部同名 `<lambda>` 会撞 hash）。
- 未知 URL Streamlit 渲染内置 404，不静默回根。

## 目标

1. **版本对齐**：项目 venv + 全局 CLI 统一 streamlit 1.59.x，先于结构改造。
2. **目录贴近 skill 模板**：`views/` → `app_pages/`；page 文件保持顶层 `def page_xxx():` 形式（**不**用 `if __name__ == "__main__"`，**不**包函数）。
3. **callable 路由**：入口用 `st.Page(page_xxx, url_path=...)` 注册；每个 page 都是模块级可 import 的 `def page_xxx() -> None:`。
4. **K 线全屏入口**：新增 `app_pages/kline_fullscreen.py::page_kline_fullscreen`，与 `page_kline` 互跳（`st.page_link`），保留 query params。
5. **去掉 `exec()` 反模式**：review_*.py 与 performance.py 改为纯函数 + 调用；状态来源切换到 query params。
6. **可逆**：5 个 commit 独立可回滚，commit 0 升级失败可立即回滚 `uv.lock`。

## 非目标

- 不升级或重写业务模块（`data.py` / `flight_kline_client.py` / `reports_server.py` / `symbol_picker.py`）。
- 不删除 `session_state` legacy 键（`selected_signals / _is_binance_page / main_signal / exchange / df / _perf_*`），仅加 `setdefault` 兜底。
- 不实现"未知 URL 自动回根"——遵循 Streamlit 默认 404 行为。
- 不动业务逻辑（Flight 拉取、signal 渲染、symbol_picker 算法）。
- 不加 `visibility="hidden"` 页。

## 架构

入口 `streamlit_app.py` 仅做三件事：

1. `start_reports_server()`（现状保留）。
2. 注册 `st.navigation(pages, position="top")`，pages 是 `dict[str, list[StreamlitPage]]`，8 个分组、24 个 page、1 个 `default=True`。
3. `pg.run()` 执行当前页。

页面模块位于 `app_pages/<name>.py`：

- 模块级 `from __future__ import annotations` + 业务 import（绝对导入，根模块）。
- 模块级 `def page_<name>() -> None:` 作为唯一入口。
- 顶层不写 `st.xxx`（除 `set_page_config`）。
- 共享 helper 在 `app_pages/_kline_common.py`（下划线前缀 = internal，**不**注册 nav）。

业务模块在项目根：`data.py / flight_kline_client.py / symbol_picker.py / performance.py / performance_table.py / utils.py / constants.py / signal_constants.py / reports_server.py`；本次全部保持原位，不迁 `utils/`。

## 文件布局与 import 调整

**目录重组**

- `views/` → `app_pages/`（一次性 `git mv`）。
- `app_pages/__init__.py` 加注释说明 internal 模块（`dashboard.py` / `kline_charts.py` / `_kline_common.py`）不进入 nav。
- 新增 `app_pages/kline_fullscreen.py`。
- 现有 `app_pages/dashboard.py`（被 `dashboard_{as,binance,em}` import）保留，加 `__all__ = [...]` 标记 internal。
- 现有 `app_pages/kline_charts.py`（被 `kline.py` import）保留，加 `__all__ = [...]` 标记 internal。

**`sys.path` hack 清理**

- `app_pages/kline.py:20` `sys.path.insert(0, os.path.dirname(os.path.dirname(...)))` 删除（streamlit run 时 `sys.path[0]` 已是项目根）。
- 同样审查并删除 `app_pages/kline_charts.py` / 根模块 `symbol_picker.py` / `performance.py` / `utils.py` 中所有 `sys.path.insert(0, ...)`。

**import 替换**

- `from views.dashboard import render_dashboard` → `from app_pages.dashboard import render_dashboard`。
- `from views.kline_charts import ...` → `from app_pages import kline_charts as kc`。
- `tests/test_kline_url.py`：`from views.kline_charts import ...` → `from app_pages import kline_charts`。

**callable 形式**

```python
# app_pages/dashboard_as.py
from __future__ import annotations
import streamlit as st
from app_pages.dashboard import render_dashboard

def page_dashboard_as() -> None:
    st.set_page_config(layout="wide", page_title="AS Dashboard")
    render_dashboard("as")
```

**入口注册**

```python
# streamlit_app.py
import streamlit as st
from reports_server import start_reports_server

from app_pages.dashboard_as import page_dashboard_as
from app_pages.dashboard_binance import page_dashboard_binance
from app_pages.dashboard_em import page_dashboard_em
from app_pages.today_opportunities import page_today_opportunities
# ... 共 24 个 import
from app_pages.kline_fullscreen import page_kline_fullscreen  # 新增

start_reports_server()

pages = {
    "Dashboard": [
        st.Page(page_dashboard_as,      title="AS",      icon="🇨🇳", url_path="dashboard_as"),
        st.Page(page_dashboard_binance, title="Binance", icon="🪙",  url_path="dashboard_binance"),
        st.Page(page_dashboard_em,      title="EM",      icon="🌍", url_path="dashboard_em"),
    ],
    "AS": [
        st.Page(page_today_opportunities, title="今日机会", icon="🎯",
                url_path="today_opportunities", default=True),
        # ... 其余 6 页显式 url_path
    ],
    "K线": [
        st.Page(page_kline,            title="K线",     icon="🕯️", url_path="kline"),
        st.Page(page_kline_fullscreen, title="K线全屏", icon="📈", url_path="kline_fullscreen"),
    ],
    # ... 其余 4 个分组
}

pg = st.navigation(pages, position="top")
pg.run()
```

## URL 映射与 default

| 分组 | callable | url_path | 备注 |
|---|---|---|---|
| Dashboard | `page_dashboard_as` | `dashboard_as` | 显式 |
| Dashboard | `page_dashboard_binance` | `dashboard_binance` | 显式 |
| Dashboard | `page_dashboard_em` | `dashboard_em` | 显式 |
| AS | `page_today_opportunities` | `today_opportunities` | **`default=True`** → 根 `/` |
| AS | `page_review_index` | `review_index` | 显式 |
| AS | `page_review_hotspot` | `review_hotspot` | 显式 |
| AS | `page_active_vol_then_nestedbc` | `active_vol_then_nestedbc` | 显式 |
| AS | `page_nested_bc` | `nested_bc` | 显式 |
| AS | `page_profit_pattern_cl3b_zsx` | `profit_pattern_cl3b_zsx` | 显式 |
| AS | `page_main_then_yd` | `main_then_yd` | 显式 |
| K线 | `page_kline` | `kline` | **保留旧 url_path 兼容直链** |
| K线 | `page_kline_fullscreen` | `kline_fullscreen` | 新增 |
| Review | `page_overview` | `overview` | 显式 |
| Review | `page_review_today` | `review_today` | 显式 |
| Review | `page_review_em` | `review_em` | 显式 |
| Review | `page_review_key` | `review_key` | 显式 |
| Reports | `page_backtest_reports` | `backtest_reports` | 显式 |
| Performance | `page_performance` | `performance` | 显式 |
| Signals | `page_all_signals_by_symbol` | `all_signals_by_symbol` | 显式 |
| Signals | `page_sector_signals` | `sector_signals` | 显式 |
| Signals | `page_search_signals` | `search_signals` | 显式 |
| Tools | `page_instrument_groups` | `instrument_groups` | 显式 |
| Tools | `page_alert_rule_crud` | `alert_rule_crud` | 显式 |
| ML | `page_ml_scores` | `ml_scores` | 显式 |

共 24 个 page，1 个 `default`，0 个 hidden。`url_path` 互不重复、与未注册的 `app_pages/dashboard` / `app_pages/kline_charts` 推断 slug 也不冲突（这些 internal 模块永远不被 `st.Page` 注册）。

`page_today_opportunities` 的 `url_path="today_opportunities"` 被 `default=True` 覆盖（属性返回 `""`），根 URL `/` 即该页。

## 跨页跳转与 query params

**跳转方式**

- K 线设置页 → 全屏页：`st.page_link(<StreamlitPage>, label="进入全屏", icon=...)`；当前 query params（`symbol/start/end/all_signals`）保留。
- 全屏页 → 设置页：相同手法反向。
- 未来编程式跳转：优先用 `st.switch_page(<StreamlitPage 对象>, query_params=...)`，**不**用字符串路径。

**query params 协议（K 线两页）**

| key | 类型 | 写入方 | 读取方 |
|---|---|---|---|
| `symbol` | 逗号分隔 token | `page_kline` | `page_kline` / `page_kline_fullscreen` |
| `start` | ISO date | `page_kline` | 同上 |
| `end` | ISO date | `page_kline` | 同上 |
| `all_signals` | `"0"` / `"1"` | `page_kline` | 同上 |

`page_kline_fullscreen` 只读不写，避免在全屏页扰动用户复制的 URL。

**Review 跳转**（去 `exec()`）

- `page_review_today` / `_em` / `_key` 改为纯函数 `build_review_<x>_params() -> dict[str, str]` + `st.page_link(_SEARCH_PAGE, query_params=...)`。
- `page_search_signals` 改为 query params 优先、`session_state` 兜底。
- 删除三处 `exec(open('search_signals.py').read())`。

**Performance 跳转**（去 `exec()`）

- 顶层 `performance.py` 主体抽成 `def render_performance(initial_signal=None, exchange="as") -> None:`，函数内仍用 `st.session_state._perf_*` 作为渲染内缓存（跨 callable 不泄漏）。
- `app_pages/performance.py` 改为单行 `render_performance()`。
- 删除 `app_pages/performance.py` 中的 `session_state.main_signal / exchange / df` 写入和 `exec()`。

## 共享模块拆分

新增 `app_pages/_kline_common.py`（下划线前缀 = internal，**不**注册 nav）：

| 现有位置 | 抽到 | 说明 |
|---|---|---|
| `app_pages/kline.py::_parse_iso_date` | `_kline_common.parse_iso_date` | 纯函数 |
| `app_pages/kline.py::_qp_str` / `_qp_bool` | `_kline_common.qp_str` / `qp_bool` | 工具 |
| `app_pages/kline.py::_group_entries` | `_kline_common.group_entries` | 纯函数 |
| `app_pages/kline.py::_fetch_groups` | `_kline_common.fetch_groups` | 调 `fkc.fetch_kline_dataframe`，无 Streamlit 副作用 |
| `app_pages/kline.py::_build_charts` | `_kline_common.build_charts` | 纯组装 |
| `app_pages/kline.py::_build_preset_name_map` / `_build_symbol_name_map` / `_symbol_label_func` / `_chart_title` | `_kline_common` 顶部 | `@st.cache_data(ttl=600)` 装饰器保持 |

`page_kline` 内部保留 `_sync_url_params`（仅设置页写 URL）与 `_redirect_when_empty`（仅设置页用）；`page_kline_fullscreen` 对空态用 `st.info` + `st.page_link` 返回设置页 + `st.stop()`。

## 跨页状态处理

| 状态键 | 现状 | 处理 |
|---|---|---|
| `session_state['_is_review_mode']` / `['_auto_select_recent_2_days']` / `['_preset_exchange']` / `['_preset_signals']` | review_*.py 写、`search_signals.py` 读 | 改 query params，session_state 加 `setdefault` 兜底 + 注释 "legacy key, no writer" |
| `session_state['main_signal']` / `['exchange']` / `['df']` / `['_perf_signal_preset_key']` / `['_perf_nm_*']` / `['_perf_grp_*']` | `app_pages/performance.py` 写、顶层 `performance.py` 读 | `session_state._perf_*` 留作渲染内缓存；`main_signal / exchange / df` 加 `setdefault` 兜底 + 注释 |
| `session_state['selected_signals']` | ml_scores / all_signals_by_symbol / search_signals 读、**无写入** | 三处各加 `setdefault("selected_signals", [])` + 注释 |
| `session_state['_is_binance_page']` | search_signals 读、**无写入** | `setdefault("_is_binance_page", False)` |
| `session_state[prefix_last_auto]` | `symbol_picker.auto_trigger` 内部哨兵 | 当前无跨页污染；约定 `key_prefix="<page>_"`，在 `symbol_picker.py` 文档加注释（不改代码） |

## 错误处理

| 场景 | 处理 |
|---|---|
| 未知 URL | Streamlit 默认 404（不静默回根） |
| K 线两页缺 `symbol` | `page_kline`：`st.info + st.stop`；`page_kline_fullscreen`：`st.info` + `st.page_link` 返回设置页 + `st.stop` |
| 缺 `start` / `end` | 回退到 `today - 365d` / `today`（仅 K 线） |
| `st.Page` 注册碰撞 | `Multiple Pages with URL pathname ...` 异常，**在测试中通过字典字面量检查**预防 |
| lambda 作 page | 禁止；所有 `page_*` 必须是模块级 `def` |
| `set_page_config` 重复调用 | Streamlit add 行为，多次调用无副作用 |
| `start_reports_server` 启动失败 | 现状不处理（非导航职责） |

## 测试策略

**`tests/test_kline_url.py`**

- import 改 `from app_pages import kline_charts`。
- 新增纯函数测试：`test_parse_iso_date / test_group_entries / test_qp_str / test_qp_bool`。
- 现有 17KB 断言（`symbol_picker` / `kline_charts` / `auto_trigger`）全部保留。

**`tests/test_review_navigation.py`（新建）**

- `test_build_review_today_params / _em / _key`：测纯函数返回 dict，无需 streamlit stub。
- redirect 走纯函数化（`build_review_today_params() -> dict[str, str]`），便于测试。

**`tests/test_navigation_registration.py`（新建，可选）**

- `streamlit_app.py` 顶部抽 `build_pages() -> dict` 函数；测试 inspect 字典字面量（分组数、page 数、url_path 互不重复、单 default）。
- **不**实例化 `st.Page`（裸 Python init 早 return）；不调 `st.navigation`。

## 迁移步骤（commit 0-5，全部可独立回滚）

### commit 0 · `chore(deps): bump streamlit 1.55 → 1.59`

- `pyproject.toml`：`"streamlit"` → `"streamlit>=1.59,<2.0"`。
- `uv lock && uv sync` 重新生成 `uv.lock`。
- 全局 CLI 对齐：`.venv/bin/streamlit` 与 `~/.local/bin/streamlit` 同为 1.59.x（venv 优先，必要时 `pip install --user --upgrade streamlit==1.59.2`）。
- 验证：版本一致；`streamlit docs st.Page / st.navigation` 字段不变；`pytest -x` 通过；`streamlit run --server.headless true` 启动 10 秒内无 `Multiple Pages / nested path` 异常；`curl /` 200；手测 `/kline?symbol=...` 直链仍带参。
- 回滚：还原 `pyproject.toml` + `uv sync`。

### commit 1 · `refactor(nav): rename views/ to app_pages/`

- `git mv views/ app_pages/`。
- `from views.xxx` → `from app_pages.xxx`（grep 全量替换）。
- 删除 `app_pages/kline.py` / `kline_charts.py` / 根模块中 `sys.path.insert(0, ...)`。
- `tests/test_kline_url.py` import 同步。
- **不**改 `streamlit_app.py` 注册结构。
- 验证：`pytest -x`；`streamlit run` 启动正常；所有现有 23 个 page（含 K 线 1 个）可访问。

### commit 2 · `refactor(nav): convert pages to callables`

- 每个 `app_pages/<name>.py` 把顶层 body 抽到 `def page_<name>() -> None:`，模块级保留业务 import。
- `streamlit_app.py` 改 import 24 个 callable，pages dict 全部用 `st.Page(callable, url_path=..., title=..., icon=...)`。
- 验证：手测 24 个 url_path 全可直链；控制台无 `Multiple Pages with URL pathname` 异常。

### commit 3 · `feat(kline): add kline_fullscreen and bidirectional page_link`

- 新增 `app_pages/kline_fullscreen.py::page_kline_fullscreen`（基于 worktree 草稿，集成进主线）。
- `streamlit_app.py` 在 K线 节并列两页。
- 两页顶部 `st.page_link` 互相跳转。
- 验证：URL 切换保留 `symbol / start / end / all_signals`。

### commit 4 · `refactor(nav): extract kline_common helpers`

- 新增 `app_pages/_kline_common.py`，移入 `parse_iso_date / qp_str / qp_bool / group_entries / fetch_groups / build_charts / build_preset_name_map / build_symbol_name_map / _symbol_label_func / _chart_title`（带 cache 装饰器）。
- `kline.py` / `kline_fullscreen.py` 改 import。
- 新增 `tests/test_kline_url.py` 纯函数测试。
- 验证：`pytest -x`；浏览器手测两页无回归。

### commit 5 · `refactor(nav): drop exec() in review_* and performance`

- `app_pages/review_*.py` 改纯函数 `build_review_<x>_params()` + `st.page_link`。
- `app_pages/performance.py` 改 `render_performance()`；顶层 `performance.py` 抽 `def render_performance(initial_signal=None, exchange="as")`。
- 所有 legacy session_state 键加 `setdefault` + 注释。
- `app_pages/search_signals.py` 改 query params 优先。
- 新增 `tests/test_review_navigation.py`。
- 验证：`pytest -x`；浏览器手测 review_* / performance 链路无回归。

## 风险与回滚

- **commit 0** 风险：1.55 → 1.59 行为差异。回滚：`uv.lock` + `pyproject.toml` revert。
- **commit 2** 风险：callable 模块名重复（lambda 闭包）。规约：所有 `page_*` 必须模块级 `def`；在 `streamlit_app.py` 加 lint 注释说明。
- **commit 3** 风险：worktree 草稿的 `kline_fullscreen.py` 集成质量未知。回滚：单 commit revert 即可。
- **commit 5** 风险：search_signals 状态来源切换最复杂。回滚：单 commit revert。

每个 commit 独立可回滚，DIFF 局部，不影响业务功能。

## 文档同步

- `AGENTS.md` 第 51-58 行：`views/` → `app_pages/`，8 分组 / 24 页结构说明。
- `openwiki/signalview.md` 第 75-78 行：目录树同步。
- `Dockerfile` 启动命令不变。
- `README.md` 启动命令不变。

## 开放问题（follow-up，不在本次范围）

1. `views/dashboard.py` / `views/kline_charts.py` 仍未从孤儿脚本变为显式 internal helper；commit 1 重命名时加 `__all__` 标记。
2. `symbol_picker.prefix_last_auto` 跨页哨兵约定（约定文档，不改代码）。
3. 未来是否对 `selected_signals` / `_is_binance_page` / `_perf_*` 等 dead-state 做清理（需先审计所有外部 import）。
4. 是否把 `pages.py` 进一步抽到 `app_pages/_pages.py` 集中注册（callable 路由成熟后的下一步）。
