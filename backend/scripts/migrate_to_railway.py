"""一站式迁移：本地 SQLite → Railway PostgreSQL"""
import json
import sqlite3
from datetime import date

DB_PATH = r"D:\claude软件\金价监测\backend\gold_monitor.db"
RAILWAY_DATABASE_URL = "postgresql://postgres:WtBVeKMnKkfaINQrknzedqqenWWKVSDC@acela.proxy.rlwy.net:13419/railway"

# ── Step 1: 从 SQLite 导出数据 ──
print("=" * 60)
print("📤 Step 1: 从本地 SQLite 导出数据")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 获取所有 table
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row["name"] for row in cursor.fetchall()]

export_data = {}
for table in tables:
    cursor.execute(f'SELECT * FROM "{table}" ORDER BY trade_date ASC')
    rows = cursor.fetchall()
    if not rows:
        continue
    records = []
    for row in rows:
        d = dict(row)
        # Convert date objects to strings
        for k, v in d.items():
            if isinstance(v, date):
                d[k] = str(v)
        records.append(d)
    export_data[table] = records
    print(f"  ✅ {table}: {len(records)} 条")

conn.close()
print(f"\n  📦 共计 {sum(len(v) for v in export_data.values())} 条数据\n")

# ── Step 2: 导入到 Railway PostgreSQL ──
print("=" * 60)
print("📥 Step 2: 导入到 Railway PostgreSQL")
print("=" * 60)

try:
    from sqlalchemy import create_engine, text
    engine = create_engine(RAILWAY_DATABASE_URL)

    with engine.connect() as pg_conn:
        # 获取已有表结构
        result = pg_conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        existing_tables = {row[0] for row in result}
        print(f"  📋 PostgreSQL 已有表: {', '.join(sorted(existing_tables))}\n")

        total_inserted = 0
        for table, records in export_data.items():
            if not records or table not in existing_tables:
                if table not in existing_tables:
                    print(f"  ⏭️  {table}: PostgreSQL 中不存在，跳过")
                continue

            # 获取列信息
            col_result = pg_conn.execute(text(
                f"SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='{table}'"
            ))
            pg_cols = {row[0] for row in col_result}

            # 只取 PostgreSQL 中存在的列
            valid_records = []
            for r in records:
                valid_r = {k: v for k, v in r.items() if k in pg_cols}
                valid_records.append(valid_r)

            if not valid_records:
                continue

            # 分批插入 (每批 500 条)
            batch_size = 500
            inserted = 0
            for i in range(0, len(valid_records), batch_size):
                batch = valid_records[i:i+batch_size]

                cols = list(batch[0].keys())
                placeholders = ", ".join([f":{c}" for c in cols])
                col_names = ", ".join(cols)

                # 使用 INSERT ... ON CONFLICT DO NOTHING 跳过重复
                try:
                    pg_conn.execute(
                        text(f"INSERT INTO \"{table}\" ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"),
                        batch
                    )
                    pg_conn.commit()
                    inserted += len(batch)
                    print(f"  ↻  {table}: 已导入 {inserted}/{len(valid_records)} 条...")
                except Exception as batch_err:
                    pg_conn.rollback()
                    print(f"  ⚠  {table} 批次错误: {batch_err}")
                    # 逐条尝试
                    for rec in batch:
                        try:
                            pg_conn.execute(
                                text(f"INSERT INTO \"{table}\" ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"),
                                rec
                            )
                            pg_conn.commit()
                            inserted += 1
                        except Exception:
                            pg_conn.rollback()

            total_inserted += inserted
            print(f"  ✅ {table}: 导入完成 ({inserted}/{len(valid_records)} 条)")

        print(f"\n  📊 总计导入: {total_inserted} 条数据")

except ImportError:
    print("  ⚠ 需要安装 sqlalchemy + psycopg2-binary")
    print("  运行: pip install sqlalchemy psycopg2-binary")
except Exception as e:
    print(f"  ❌ 连接 PostgreSQL 失败: {e}")

print("\n" + "=" * 60)
print("✅ 迁移完成！")
print("=" * 60)
