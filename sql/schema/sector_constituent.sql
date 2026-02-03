-- 板块成分股关系表
CREATE TABLE sector_constituent (
    id BIGSERIAL PRIMARY KEY,
    sector_symbol VARCHAR(20) NOT NULL,
    sector_name VARCHAR(100),
    sector_exchange VARCHAR(10) NOT NULL,
    stock_symbol VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    stock_exchange VARCHAR(10) NOT NULL,
    snapshot_date DATE NOT NULL,
    weight DECIMAL(10, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_sector_stock_snapshot_date UNIQUE (sector_symbol, sector_exchange, stock_symbol, stock_exchange, snapshot_date)
);

CREATE INDEX idx_sector_constituent_sector_date ON sector_constituent(sector_symbol, sector_exchange, snapshot_date DESC);
CREATE INDEX idx_sector_constituent_stock_date ON sector_constituent(stock_symbol, stock_exchange, snapshot_date DESC);
CREATE INDEX idx_sector_constituent_snapshot_date ON sector_constituent(snapshot_date DESC);

COMMENT ON TABLE sector_constituent IS '板块与个股的成分股关系表（按日期存储快照）';
COMMENT ON COLUMN sector_constituent.sector_symbol IS '板块代码';
COMMENT ON COLUMN sector_constituent.sector_name IS '板块名称';
COMMENT ON COLUMN sector_constituent.sector_exchange IS '板块交易所 (em/asindex等)';
COMMENT ON COLUMN sector_constituent.stock_symbol IS '个股代码';
COMMENT ON COLUMN sector_constituent.stock_name IS '个股名称';
COMMENT ON COLUMN sector_constituent.stock_exchange IS '个股交易所 (as/em等)';
COMMENT ON COLUMN sector_constituent.snapshot_date IS '快照日期，表示这是哪一天的成分股关系';
COMMENT ON COLUMN sector_constituent.weight IS '权重(可选)';
