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

## 数据库连接（任选其一）

1. 环境变量 `POSTGRESQL_URL` 或 `DATABASE_URL`
2. 在**仓库根目录**（或上级目录）放置与 Streamlit 相同的 `.streamlit/secrets.toml`，内含 `[connections.quantdb] url = "postgresql://..."`（训练命令会自动向上查找该文件）
3. 命令行：`signalml-train train --db-url postgresql://...`
4. 指定文件：`signalml-train train --secrets /path/to/secrets.toml`

## 训练

```bash
signalml-train train --days 180 --horizon 5 --out ./artifacts/run1
```

或使用模块方式：

```bash
python -m signalml train --days 180 --horizon 5 --out ./artifacts/run1
```

## 可视化

训练完成后在 signalview 侧设置 `SIGNALML_ARTIFACT_DIR` 指向 `--out` 目录（内含 `model.joblib` 与 `meta.yaml`），打开 **ML Scores** 页面。
