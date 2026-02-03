#!/usr/bin/env python3
"""简单测试数据库连接"""
import time
import socket

# 首先测试网络连通性
host = "ep-autumn-bush-a1w986x8-pooler.ap-southeast-1.aws.neon.tech"
print(f"1️⃣ 测试网络连通性到 {host}...")

start = time.time()
try:
    socket.setdefaulttimeout(5)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, 5432))
    elapsed = time.time() - start
    if result == 0:
        print(f"   ✅ 端口 5432 可达，耗时: {elapsed:.2f}秒")
    else:
        print(f"   ❌ 端口 5432 不可达 (错误码: {result})")
    sock.close()
except socket.timeout:
    print(f"   ❌ 连接超时 (>5秒)")
except Exception as e:
    print(f"   ❌ 网络错误: {e}")

# 测试 DNS 解析
print(f"\n2️⃣ 测试 DNS 解析...")
start = time.time()
try:
    ip = socket.gethostbyname(host)
    elapsed = time.time() - start
    print(f"   ✅ DNS 解析: {ip}，耗时: {elapsed:.2f}秒")
except Exception as e:
    print(f"   ❌ DNS 解析失败: {e}")

# 测试数据库连接
print(f"\n3️⃣ 测试数据库连接...")
try:
    import psycopg
    
    # 注意：移除 channel_binding=require 参数试试
    conn_str = "postgresql://neondb_owner:npg_Y4lbrVAmXiP2@ep-autumn-bush-a1w986x8-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
    
    start = time.time()
    conn = psycopg.connect(conn_str, connect_timeout=10)
    elapsed = time.time() - start
    print(f"   ✅ 数据库连接成功！耗时: {elapsed:.2f}秒")
    
    # 简单查询
    print(f"\n4️⃣ 测试简单查询...")
    start = time.time()
    cur = conn.execute("SELECT COUNT(*) FROM signal")
    count = cur.fetchone()[0]
    elapsed = time.time() - start
    print(f"   ✅ signal 表有 {count:,} 行，耗时: {elapsed:.2f}秒")
    
    conn.close()
except Exception as e:
    elapsed = time.time() - start
    print(f"   ❌ 连接失败 (耗时 {elapsed:.2f}秒): {e}")
