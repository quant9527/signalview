#!/usr/bin/env python3
"""诊断 SQL 查询性能问题"""

import tomllib
from pathlib import Path


def load_secrets():
    """加载 secrets.toml 配置"""
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        print(f"❌ 找不到配置文件: {secrets_path}")
        return None
    
    with open(secrets_path, "rb") as f:
        return tomllib.load(f)


def diagnose():
    """诊断数据库连接和查询性能"""
    import time
    
    secrets = load_secrets()
    if not secrets:
        return
    
    conn_str = secrets.get("connections", {}).get("postgresql", {}).get("url")
    if not conn_str:
        print("❌ 未找到数据库连接字符串")
        return
    
    # 隐藏密码显示连接信息
    import re
    safe_conn = re.sub(r':([^:@]+)@', ':***@', conn_str)
    print(f"📡 连接字符串: {safe_conn}\n")
    
    try:
        import psycopg
    except ImportError:
        print("❌ 请安装 psycopg: pip install psycopg[binary]")
        return
    
    # 测试连接
    print("=" * 60)
    print("1️⃣  测试数据库连接")
    print("=" * 60)
    
    start = time.time()
    try:
        conn = psycopg.connect(conn_str, connect_timeout=10)
        elapsed = time.time() - start
        print(f"✅ 连接成功! 耗时: {elapsed:.2f} 秒")
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ 连接失败 (耗时 {elapsed:.2f} 秒): {e}")
        return
    
    with conn:
        with conn.cursor() as cur:
            # 检查表信息
            print("\n" + "=" * 60)
            print("2️⃣  检查 signal 表信息")
            print("=" * 60)
            
            # 表大小
            cur.execute("""
                SELECT 
                    pg_size_pretty(pg_total_relation_size('signal')) as total_size,
                    pg_size_pretty(pg_relation_size('signal')) as table_size,
                    pg_size_pretty(pg_indexes_size('signal')) as index_size
            """)
            row = cur.fetchone()
            print(f"📊 表总大小: {row[0]}")
            print(f"   - 数据大小: {row[1]}")
            print(f"   - 索引大小: {row[2]}")
            
            # 行数统计
            cur.execute("SELECT COUNT(*) FROM signal")
            count = cur.fetchone()[0]
            print(f"📈 总行数: {count:,}")
            
            # 检查索引
            print("\n" + "=" * 60)
            print("3️⃣  检查现有索引")
            print("=" * 60)
            
            cur.execute("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'signal'
                ORDER BY indexname
            """)
            indexes = cur.fetchall()
            if indexes:
                for idx_name, idx_def in indexes:
                    print(f"✅ {idx_name}")
                    print(f"   {idx_def}\n")
            else:
                print("⚠️  没有找到索引!")
            
            # EXPLAIN ANALYZE 查询
            print("=" * 60)
            print("4️⃣  分析查询执行计划 (45天数据)")
            print("=" * 60)
            
            query = """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
            SELECT DISTINCT ON (symbol, signal_name, signal_date, exchange, freq) *
            FROM signal
            WHERE signal_date >= now() - interval '45 days'
            ORDER BY symbol, signal_name, signal_date DESC, exchange, freq
            """
            
            start = time.time()
            cur.execute(query)
            elapsed = time.time() - start
            
            print(f"\n⏱️  查询执行耗时: {elapsed:.2f} 秒\n")
            print("执行计划:")
            print("-" * 60)
            for row in cur.fetchall():
                print(row[0])
            
            # 测试实际查询时间
            print("\n" + "=" * 60)
            print("5️⃣  测试实际查询时间")
            print("=" * 60)
            
            query_actual = """
            SELECT DISTINCT ON (symbol, signal_name, signal_date, exchange, freq) *
            FROM signal
            WHERE signal_date >= now() - interval '45 days'
            ORDER BY symbol, signal_name, signal_date DESC, exchange, freq
            """
            
            start = time.time()
            cur.execute(query_actual)
            rows = cur.fetchall()
            elapsed = time.time() - start
            
            print(f"✅ 查询返回 {len(rows):,} 行")
            print(f"⏱️  总耗时: {elapsed:.2f} 秒")
            
            if elapsed > 2:
                print("\n⚠️  查询较慢，建议添加以下索引:")
                print("-" * 60)
                print("""
-- 为 signal_date 添加索引 (加速 WHERE 条件)
CREATE INDEX idx_signal_date ON signal(signal_date DESC);

-- 为 DISTINCT ON 列组合添加索引
CREATE INDEX idx_signal_composite ON signal(symbol, signal_name, signal_date DESC, exchange, freq);
                """)
            else:
                print("\n✅ 查询性能良好!")


if __name__ == "__main__":
    diagnose()
