-- 自选股分组表
CREATE TABLE instrument_group (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uk_instrument_group_name UNIQUE (name)
);

COMMENT ON TABLE instrument_group IS '自选股分组表，用于管理自定义标的分组';
COMMENT ON COLUMN instrument_group.name IS '分组名称，如 position';
COMMENT ON COLUMN instrument_group.description IS '分组描述';

-- 自选股分组成員表
CREATE TABLE instrument_group_member (
    id BIGSERIAL PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uk_group_member UNIQUE (group_name, exchange, symbol),
    CONSTRAINT fk_group_member_group FOREIGN KEY (group_name) REFERENCES instrument_group(name) ON DELETE CASCADE
);

CREATE INDEX idx_instrument_group_member_group ON instrument_group_member(group_name);
CREATE INDEX idx_instrument_group_member_symbol ON instrument_group_member(exchange, symbol);

COMMENT ON TABLE instrument_group_member IS '自选股分组成員表，记录每个分组包含的标的';
COMMENT ON COLUMN instrument_group_member.group_name IS '所属分组名称';
COMMENT ON COLUMN instrument_group_member.exchange IS '标的交易所';
COMMENT ON COLUMN instrument_group_member.symbol IS '标的代码';
