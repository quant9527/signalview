-- signal 表性能优化索引
-- 针对查询: DISTINCT ON (symbol, signal_name, signal_date, exchange, freq)
--          ORDER BY symbol, signal_name, signal_date DESC, exchange, freq
--          WHERE signal_date >= now() - interval 'N days'

-- 关键！复合索引必须与 DISTINCT ON / ORDER BY 顺序完全一致
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signal_distinct_on
ON signal(symbol, signal_name, signal_date DESC, exchange, freq);

-- 分析表以更新统计信息
ANALYZE signal;

-- 验证索引
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'signal';
