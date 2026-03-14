#!/usr/bin/env python3
"""用与 app 相同的连接查询 signal 表：信号名、freq 分布等。"""
import os
import sys

def get_conn_str():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    path = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
    if os.path.isfile(path):
        with open(path, "rb") as f:
            s = tomllib.load(f)
        return s.get("connections", {}).get("quantdb", {}).get("url")
    return os.environ.get("POSTGRESQL_URL") or os.environ.get("DATABASE_URL")

def main():
    conn_str = get_conn_str()
    if not conn_str:
        print("未找到连接配置：.streamlit/secrets.toml 或环境变量 POSTGRESQL_URL/DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    import psycopg
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # 最近 45 天总条数
            cur.execute("""
                SELECT COUNT(*) FROM signal
                WHERE signal_date >= now() - interval '45 days'
            """)
            total = cur.fetchone()[0]
            print(f"最近 45 天 signal 总条数: {total}")

            # signal_name 分布（前 20）
            cur.execute("""
                SELECT signal_name, COUNT(*) AS cnt
                FROM signal
                WHERE signal_date >= now() - interval '45 days'
                GROUP BY signal_name
                ORDER BY cnt DESC
                LIMIT 20
            """)
            print("\nsignal_name 分布 (TOP 20):")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]}")

            # nested_2bc 的 freq 分布
            cur.execute("""
                SELECT freq, COUNT(*) AS cnt
                FROM signal
                WHERE signal_date >= now() - interval '45 days'
                  AND signal_name LIKE 'nested_2bc%'
                GROUP BY freq
                ORDER BY cnt DESC
            """)
            rows = cur.fetchall()
            print("\nnested_2bc* 的 freq 分布:")
            if not rows:
                print("  (无)")
            else:
                for row in rows:
                    print(f"  {row[0]}: {row[1]}")

            # 5m/15m 的 nested_2bc 条数（不区分大小写）
            cur.execute("""
                SELECT COUNT(*) FROM signal
                WHERE signal_date >= now() - interval '45 days'
                  AND signal_name LIKE 'nested_2bc%'
                  AND LOWER(TRIM(freq::text)) IN ('5m', '15m')
            """)
            n_5m15m = cur.fetchone()[0]
            print(f"\nnested_2bc* 且 freq 为 5m/15m 的条数: {n_5m15m}")

if __name__ == "__main__":
    main()
