<!-- Parent: ../../../AGENTS.md -->
<!-- Generated: 2026-05-08 | Updated: 2026-05-08 -->

# signalml

## Purpose
Machine learning pipeline for signal prediction and backtesting. Trains models on historical kline features and sector resonance data to predict future signal performance.

## Key Files
| File | Description |
|------|-------------|
| `cli.py` | Command-line interface for train/predict/backtest workflows |
| `train.py` | Model training — feature engineering + ML model fitting |
| `predict.py` | Inference — load trained model and predict on new data |
| `backtest.py` | Backtesting engine for evaluating predictions |
| `db.py` | Database operations — read signals, klines, features from PostgreSQL |
| `features.py` | Feature engineering for ML (base features) |
| `features_kline.py` | K-line specific features (OHLCV patterns) |
| `features_resonance.py` | Sector resonance features for ML |
| `labels.py` | Label generation for supervised learning |
| `prices.py` | Price data utilities |
| `flight_kline.py` | Flight K-line data client integration |
| `dates.py` | Date/time utilities for trading calendar |
| `__init__.py` | Package init |
| `__main__.py` | Module entry point |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `__pycache__/` | Python bytecode cache |

## For AI Agents

### Working In This Directory
- Train: `python -m signalml.src.signalml train` (see `cli.py` for full args)
- Predict: `python -m signalml.src.signalml predict`
- Backtest: `python -m signalml.src.signalml backtest`
- Features are computed from PostgreSQL kline + signal tables

### Testing Requirements
- Validate model accuracy on holdout set
- Backtest results should beat baseline (random or buy-and-hold)

### Common Patterns
- Feature pipeline: `db.py` → `features*.py` → `train.py`
- Prediction pipeline: `db.py` → `features*.py` → `predict.py`
- All features cached in `.cache/signalml/` for incremental builds

## Dependencies

### Internal
- `signalview/data.py` — PostgreSQL connection (shared)
- `signalview/constants.py` — app constants

### External
- scikit-learn — ML models
- pandas, numpy — data processing
- psycopg2 — PostgreSQL client
- akshare — A-share market data

<!-- MANUAL: -->
