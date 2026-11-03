-- 策略说明与策略案例。
-- 已有 signal_lab_case 的库不要直接执行本文件建案例表，
-- 用 scripts/seed_strategy.py 改名并写入核心思想。
-- 该脚本会留下视图 signal_lab_case，供尚未更新的旧进程读取。

CREATE TABLE IF NOT EXISTS strategy (
    name        text PRIMARY KEY,
    core_idea   text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT ck_strategy_name_nonempty CHECK (btrim(name) <> '')
);

COMMENT ON TABLE strategy IS '策略说明，一行一个策略';
COMMENT ON COLUMN strategy.name IS '策略名，与 strategy_case.strategy 相同';
COMMENT ON COLUMN strategy.core_idea IS '策略核心思想';
COMMENT ON COLUMN strategy.created_at IS '首次写入时间';
COMMENT ON COLUMN strategy.updated_at IS '最后修改时间';

CREATE TABLE IF NOT EXISTS strategy_case (
    id          text PRIMARY KEY,
    name        text NOT NULL DEFAULT '',
    signal_date date NOT NULL,
    signal_at   timestamp,
    symbol_id   text NOT NULL,
    signal      text NOT NULL DEFAULT '',
    strategy    text NOT NULL DEFAULT '',
    info        text NOT NULL DEFAULT '',
    note        text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_case_date
    ON strategy_case (signal_date DESC);

COMMENT ON TABLE strategy_case IS '策略案例';
COMMENT ON COLUMN strategy_case.id IS '飞书记录 id';
COMMENT ON COLUMN strategy_case.name IS '案例名称';
COMMENT ON COLUMN strategy_case.signal_date IS '信号日期';
COMMENT ON COLUMN strategy_case.signal_at IS '案例时间，含时分。空表示还没改过，详情用 K 线时间';
COMMENT ON COLUMN strategy_case.symbol_id IS '标的代码，如 as:688802:2h';
COMMENT ON COLUMN strategy_case.signal IS '信号类型，如 BUY';
COMMENT ON COLUMN strategy_case.strategy IS '策略名，对应 strategy.name';
COMMENT ON COLUMN strategy_case.info IS '案例信息';
COMMENT ON COLUMN strategy_case.note IS '注意点';
