# signalml

独立包：从 PostgreSQL 读取 `signal` 表，拉取 A 股日线，构造标签与极简特征，训练 `sklearn` 的梯度提升回归，导出模型供 signalview 可视化打分。

## 安装

在仓库根目录：

```bash
uv sync --extra ml
```

或仅安装本包：

```bash
cd signalml && pip install -e .
```

## K 线数据源（训练标签依赖日线）

与 **signalview** 共用仓库根目录的 [`flight_kline_client.py`](../flight_kline_client.py)。Flight `tags` 示例：`as_600519_1d`（个股）；**沪深300** 为 **`asindex_sh000300_1d`**（`exchange=asindex`，代码 `sh000300`，勿用 `as_000300_1d`）。

- 环境变量 **`FLIGHT_URL`**（默认 `grpc://127.0.0.1:50001`）
- **`SIGNALML_KLINE_SOURCE`**：
  - `flight_first`（默认）：先批量 Flight，缺标的再 **akshare**
  - `flight`：仅 Flight，失败不补 akshare
  - `akshare`：仅 akshare

Flight 返回表中的**数值列**（如 `ma5ma10_jc`、`ma5ma10_sc` 等）会一并写入缓存 parquet，供后续扩展特征使用。

## 数据库连接（任选其一）

与 Streamlit 对齐：**`DATABASE_URL`**（12-factor 惯例），或 `.streamlit/secrets.toml` 里的 `[connections.quantdb] url`。

1. 环境变量 **`DATABASE_URL`**
2. **`.streamlit/secrets.toml`**（训练会从当前目录向上查找）
3. 命令行覆盖：`signalml-train train --db-url postgresql://...` 或 `--secrets /path/to/secrets.toml`

优先级：`--db-url` > `DATABASE_URL` > secrets。

### 用 `.env` 省去长命令行

在**当前工作目录或上级目录**放置 `.env`（`python-dotenv` 自动向上查找），或在启动前设置 **`SIGNALML_ENV_FILE`** 指向任意路径；也可用 **`signalml-train train --env-file /path/.env`**。

模板：仓库根目录 **[`.env.example`](../.env.example)**，可执行 `cp .env.example .env` 再填写数据库等敏感项。

已写入进程的**环境变量优先**于 `.env` 中的同名项（`override=False`）。常用键：

| 变量 | 对应参数 |
|------|----------|
| `DATABASE_URL` | Postgres 连接串（与 Streamlit 共用；也可用 `.streamlit/secrets.toml`） |
| `SIGNALML_SECRETS` | `--secrets` |
| `SIGNALML_DAYS` | `--days` |
| `SIGNALML_HORIZON` | `--horizon` |
| `SIGNALML_OUT` | `--out`（必填之一：命令行或本变量） |
| `SIGNALML_CACHE` | `--cache` |
| `SIGNALML_EXCHANGE` | `--exchange` |
| `SIGNALML_TEST_RATIO` | `--test-ratio` |
| `SIGNALML_RESONANCE_DAYS` | `--resonance-days` |
| `SIGNALML_THS_SIGNAL_FILTER` | `--ths-signal-filter` |
| `SIGNALML_THS_POSITION` | `--ths-position` |
| `SIGNALML_NO_RESONANCE` | 设为 `1` / `true` / `yes` / `on` 等价于 `--no-resonance` |
| `SIGNALML_NO_THS_RESONANCE` | 同上，等价于 `--no-ths-resonance` |
| `SIGNALML_NO_KLINE_MARKET` | 同上，等价于 `--no-kline-market` |

配置好后可简写为：

```bash
signalml-train train
```

（仍需能通过上述任一方式解析到数据库 URL，且 `SIGNALML_OUT` 或 `--out` 已设置。）

## 训练

```bash
signalml-train train --days 180 --horizon 5 --out ./artifacts/run1
```

### 共振特征（默认开启）

在回看窗口 **L 个日历日** `[signal_date - L, signal_date]` 内（且仅统计 **不晚于该条 signal_date** 的信号，避免用未来信息）：

- **同 symbol**：信号条数、`signal_name` 去重数、`freq` 去重数（多周期共振）、是否多 `freq` 并存
- **THS 板块**：用表 `sector_constituent`（`sector_exchange='ths'`, `stock_exchange='as'`）最新快照，把个股映射到板块/指数代码，统计这些 THS `symbol` 上同期 THS 信号条数

可选参数：

- `--resonance-days 5`、`--no-resonance`、`--no-ths-resonance`
- **`--ths-position long`**（或 `short`）：只统计 `signal` 表里 **`side` 列**与该值匹配的 THS 信号（大小写不敏感，需与库中实际取值一致，如 `long`/`short`）
- `--ths-signal-filter 子串`：在 `side` 筛选之后，再要求 `signal_name` 包含该子串（可选叠加）

说明：若要在标签上对齐「板块信号略晚于个股」这类关系，需要单独定义决策时点或标签，当前实现刻意不在个股信号日之后读取板块信号，以防标签泄漏。

或使用模块方式：

```bash
python -m signalml train --days 180 --horizon 5 --out ./artifacts/run1
```

## 可视化

训练完成后在 signalview 侧设置 `SIGNALML_ARTIFACT_DIR` 指向 `--out` 目录（内含 `model.joblib` 与 `meta.yaml`），打开 **ML Scores** 页面。
