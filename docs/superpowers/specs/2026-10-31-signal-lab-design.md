# SIGNAL LAB — 策略案例图库页面设计

日期：2026-10-31
仓库：signalview

## 背景

参考飞书「策略库」多维表格中的 Base Vibe 自定义页面（SIGNAL LAB 策略案例图库），在
signalview（Streamlit）实现同等体验的案例浏览页面。参考页效果：

- 顶栏 `SIGNAL LAB` +「策略案例图库」，统计（案例总数 / 信号类数）
- 筛选：策略下拉、案例名搜索框、信号类型 chips（全部/BUY/SELL/IGNORE_BUY/NOT_BUY/LONG / BUY）
- 卡片墙：K 线图 + 信号徽章叠加 + 标题 + 日期 + 查看详情，分页（每页 28 张）
- 详情弹窗：左侧 K 线大图，右侧字段（日期/标的代码/信息），可在同一策略的案例间左右翻动

## 数据契约

来源：飞书「策略库」bitable（base token `M3Yvbt032aq8smsSi1BcrLisn9g`，
策略案例表 `tblW6XBSpDRg3Q44`，328 条；策略表 `tblnX5PqCCrMthgZ`）。
通过浏览器内已登录会话抓取 records API（base64+gzip 编码，需解压），
生成静态文件 `data/signal_lab_cases.json` 提交进仓库。抓取脚本
`scripts/fetch_signal_lab.py` 保存抓取用的 JS 片段与解码逻辑说明，便于日后更新数据。

```json
{
  "cases": [
    {
      "id": "recvhjfSI3YVVc",
      "name": "闽东电力",
      "date": "2025-07-27",            // 来自 date 毫秒时间戳
      "code": "as:000993:1h",          // symbol_id: exchange:symbol:freq
      "signal": "BUY",                 // 单选选项名（opt id 解析后）
      "strategy": "bc_xd4",            // signal_name 链接字段 → 策略表记录名
      "info": "2h MACD金叉触发四段下跌背驰",
      "note": ""                       // 注意点
    }
  ]
}
```

- 页面运行时只读该 JSON，与 PG、飞书解耦。
- 文件缺失/字段缺失：页面顶部 `st.error` 明确提示，不崩溃。
- 字段解析规则：`code` 按 `exchange:symbol:freq` 拆分；无法解析的记录保留原串并跳过 K 线渲染。

## 页面结构

新文件 `app_pages/signal_lab.py`，注册到 `streamlit_app.py` 新分区「案例库」
（icon `:material/lab_panel:`，url_path `signal_lab`）。

1. **顶栏**：`SIGNAL LAB` 标题 +「策略案例图库」副标题 + 统计（N 个案例 / M 类信号）
2. **筛选区**（原生组件）：
   - 策略：`st.selectbox`（全部策略 + 各策略，选项数 = 去重 strategy）
   - 案例名：`st.text_input`（子串匹配 name）
   - 信号：`st.pills` 单选（全部 + JSON 中出现的 signal 值）
   - 三者组合过滤，结果为「当前案例列表」（排序：date 降序）
3. **卡片墙**（`st.components.v2.component` 自定义组件，整墙 1 个 widget）：
   - 分页：每页 28 张，分页条在组件内，切页通过事件回传 Python 重新生成该页缩略图
   - 每张卡片：缩略图（base64 PNG）+ 左上角信号徽章（颜色按 signal 类型）+
     「查看详情」浮层 + 标题 + 日期；hover 效果 CSS 实现
   - 点击卡片：组件回传 case id → 打开详情弹窗
4. **详情弹窗**（`@st.dialog`）：
   - 左：完整 echarts K 线（复用 `kline_charts` 管线：MA/成交量/MACD + 信号日标注）
   - 右：字段列表（日期/标的代码/信息/策略/注意点）
   - 底部「上一个 / 下一个」：在**当前筛选下同策略**的案例列表内循环翻动
5. **页脚**：`SIGNAL LAB © 2026 策略案例图库 · 共 N 个案例`

## 缩略图

`app_pages/_signal_lab_thumbs.py`：

- 自绘 SVG 迷你蜡烛图（零新依赖，matplotlib 不在项目依赖里）+ 成交量柱，
  无坐标轴、留白极小
- 数据：flight K 线客户端按 (exchange, freq) 分组批量拉取；窗口 = 案例日期
  前 60 根 + 后 20 根，案例日虚线标记
- SVG 字符串直接内嵌组件；`st.cache_data`（key = `code|date`，`max_entries` 限制）
  ；拉取失败返回占位 SVG，不阻塞整页
- 每次翻页只为当前页 28 张生成/取缓存

## 详情大图

复用 `kline_charts.py` 的 `extract_symbol_data → to_echarts_* → build_chart_meta`
管线，锚定案例日期，信号点箭头标注。K 线不可用时弹窗右侧仍显示字段信息。

## 文件组织

| 文件 | 职责 |
|------|------|
| `app_pages/signal_lab.py` | 页面主体：读 JSON、筛选、调度卡片墙与弹窗 |
| `app_pages/_signal_lab_data.py` | 数据加载/校验/筛选/分页纯函数 |
| `app_pages/_signal_lab_gallery.py` | CCv2 卡片墙组件（HTML/CSS/JS 模板 + 事件回传） |
| `app_pages/_signal_lab_thumbs.py` | SVG 缩略图生成与缓存 |
| `data/signal_lab_cases.json` | 案例静态数据 |
| `scripts/fetch_signal_lab.py` | 数据抓取说明/脚本 |
| `tests/test_signal_lab.py` | 单测 |

## 错误处理

- JSON 缺失/损坏 → `st.error` + 停止渲染
- `code` 无法解析或 K 线拉取失败 → 卡片/弹窗显示占位图与提示，页面其余部分正常
- 翻页/弹窗索引越界 → 取模循环，不抛异常

## 测试

- `_signal_lab_thumbs`：给定合成 OHLC DataFrame，生成非空 SVG；窗口截取正确
- JSON 加载：正常/缺失/字段缺失三种输入
- 筛选、分页与卡片 payload 构造逻辑：纯函数级单测
- 浏览器手工验收：卡片墙视觉、弹窗交互、翻页（实现计划 Task 6）

## 非目标

- 详情弹窗键盘左右键导航（Streamlit 弹窗内键盘捕获不可靠）
- 飞书附件图片下载与展示（字段本身为空）
- 案例数据的在线编辑/回写飞书
