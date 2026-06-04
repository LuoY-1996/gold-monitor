import psycopg2
PG = "postgresql://postgres:WtBVeKMnKkfaINQrknzedqqenWWKVSDC@acela.proxy.rlwy.net:13419/railway"
pg = psycopg2.connect(PG)
cur = pg.cursor()
cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_catalog='railway'")
rows = cur.fetchall()
print("All tables:")
for s, t in rows:
    print(f"  {s}.{t}")
cur.execute("SELECT current_schema")
print(f"Current schema: {cur.fetchone()[0]}")
# Also list schemas
cur.execute("SELECT schema_name FROM information_schema.schemata")
schemas = [r[0] for r in cur.fetchall()]
print(f"All schemas: {schemas}")
cur.close(); pg.close()
