<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-29 | Updated: 2026-06-29 -->

# signalview - 信号可视化面板

## Purpose
**信号展示和绩效分析面板**。基于 Streamlit 的 Web 应用 (:8501)，从 PostgreSQL 读取交易信号数据，提供概览、排名、市场对比等可视化功能。

## 服务架构

```
atlas/consumer → 写入信号到 PostgreSQL public.signal 表
        │
        ▼
┌───────────────────────────────────────────┐
│  signalview (Streamlit :8501)             │
│                                           │
│  ┌───────────────────────────────────┐    │
│  │  三个核心页面 (Streamlit)          │    │
│  │                                   │    │
│  │  📊 Overview 概览                  │    │
│  │  ├── 信号总数 / 今日新增           │    │
│  │  ├── 策略分布柱状图                │    │
│  │  └── 信号时间线                    │    │
│  │                                   │    │
│  │  🏆 Top Score 排行榜               │    │
│  │  ├── 评分最高的信号排名             │    │
│  │  └── 信号详情查看                  │    │
│  │                                   │    │
│  │  📈 Market 市场对比                │    │
│  │  ├── 当前价格 vs 信号价格           │    │
│  │  ├── 涨跌幅计算                    │    │
│  │  └── CSV 导出                     │    │
│  └───────────────────────────────────┘    │
│                                           │
│  ┌───────────────────────────────────┐    │
│  │  signalml/ 信号 ML 分析            │    │
│  │  机器学习模型对信号进行二次分析      │    │
│  └───────────────────────────────────┘    │
└───────────────────────────────────────────┘
        │
        ▼
  akshare (行情对比) / Flight K-line (K线数据)
```

## 关键文件

| 文件 | 描述 |
|------|------|
| `streamlit_app.py` | Streamlit 应用入口 |
| `data.py` | PostgreSQL 数据获取和信号加载 |
| `performance.py` | 绩效指标计算 |
| `performance_table.py` | 绩效表格渲染 |
| `constants.py` | 应用常量 |
| `signal_constants.py` | 信号相关常量 |
| `utils.py` | 工具函数 |
| `flight_kline_client.py` | Flight K 线客户端 |
| `views/` | Streamlit 页面模块目录 |

## 目录

| 目录 | 用途 |
|------|------|
| `views/` | Streamlit 页面模块 |
| `signalml/` | ML 模型工件和信号缓存 |
| `sql/schema/` | 数据库 schema 定义 |
| `sql/data/` | 种子/参考数据 |
| `scripts/` | 信号处理脚本 |

## 数据来源

| 来源 | 用途 | 地址 |
|------|------|------|
| **PostgreSQL** | 信号数据主来源 | `signal` 表 (由 atlas/consumer 写入) |
| **akshare** | 当前行情对比 | HTTP API (可选，Market 页面使用) |
| **Flight K-line** | K 线数据 | gRPC Arrow Flight :50001 |

## 依赖关系

### 被依赖
- 无（终端展示层，不提供服务给其他模块）

### 依赖
- **atlas/consumer** — 写入 PostgreSQL signal 表（如果没有新信号，说明数据流 upstream 有问题）
- PostgreSQL — 数据库
- `ops/app/compose.yaml` — signalview 容器配置

## 问题排查指引

| 问题 | 排查方向 |
|------|----------|
| Streamlit 页面打不开 | 检查 signalview 容器状态 :8501 |
| 没有信号数据 | 检查 PostgreSQL signal 表是否有数据 → 确认 atlas/consumer 是否正常运行 |
| 页面数据不更新 | 检查 consumer 是否在消费 Kafka signal topic |
| 行情对比不显示 | akshare 是否可用 / `data.py` 中 `conn_str` 配置是否正确 |
| 页面报错 | 检查 .streamlit/secrets.toml 或环境变量配置 |

## For AI Agents

### Working In This Directory
- 运行: `streamlit run streamlit_app.py`
- 所有时间戳为 Asia/Shanghai (UTC+8)
- 无需测试套件 — 通过 Streamlit UI 手动验证
- SQL schema 在 `sql/schema/`，必须与 `data.py` 预期匹配

### 重要配置
- PostgreSQL `conn_str` 定义在 `streamlit_app.py` 中
- Docker 部署时 `.streamlit` 目录通过 volume 挂载

<!-- MANUAL: -->
