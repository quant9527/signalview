-- signal 表索引（与本仓库实际查询一致）
--
-- 来源：data.load_data、signalml.db.load_signals、scripts/query_signals.py
-- 典型 WHERE：
--   signal_date >= ... [AND signal_date < ...]
--   以及可选 AND signal_name LIKE 'prefix%'
-- ORDER BY signal_date DESC
--
-- 说明：唯一约束 unique_signal_per_day 的首列是 pick_id，不是 signal_date，
-- 无法高效支持「按日期窗口扫表」，需单独 btree。

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signal_signal_date_desc_signal_name
ON signal (signal_date DESC, signal_name);

ANALYZE signal;

-- 验证：SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'signal';
