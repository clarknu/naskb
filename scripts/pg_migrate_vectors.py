"""建 PG 向量表 + 从本地索引迁移数据到 PostgreSQL pgvector。

用法：
  python pg_migrate_vectors.py          # 建表 + 迁移
  python pg_migrate_vectors.py --drop   # 先删旧表再重建
"""
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "naskb" / "scripts"))

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from naskb.common.config import Config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop", action="store_true", help="先删旧表再重建")
    args = parser.parse_args()

    work_path = str(Path(__file__).parent.parent / "NASKB_data")
    config = Config.from_work_path(work_path)
    npz_path = Path(work_path) / "db" / "vectors.npz"
    json_path = Path(work_path) / "db" / "vectors.json"

    if not npz_path.exists() or not json_path.exists():
        print("[ERROR] 本地向量索引不存在，请先运行 build_vectors.py")
        return

    # 加载本地索引
    print("[1/4] 加载本地向量索引...")
    data = np.load(str(npz_path), allow_pickle=False)
    mat = data["mat"]
    with open(json_path, encoding="utf-8") as f:
        meta = json.load(f)
    n = len(meta["paths"])
    print(f"  → {n} 条描述, {mat.shape[1]} 维向量")

    # 连接 PG
    print("[2/4] 连接 PostgreSQL...")
    conn = psycopg2.connect(
        host=config.pg_host, port=config.pg_port,
        user=config.pg_user, password=config.pg_password,
        dbname=config.pg_database, connect_timeout=10
    )
    register_vector(conn)
    cur = conn.cursor()
    table = config.pg_vector_table
    dim = config.pg_vector_dim
    print(f"  → 已连接 {config.pg_database}")

    # 建表
    print("[3/4] 建向量表...")
    if args.drop:
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"  → 已删除旧表 {table}")

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id          SERIAL PRIMARY KEY,
            path        TEXT NOT NULL UNIQUE,
            kind        TEXT NOT NULL DEFAULT 'file',
            summary     TEXT,
            category    TEXT,
            tags        TEXT[],
            text_index  TEXT,
            context     TEXT,
            embedding   vector({dim}),
            created_at  TIMESTAMPTZ DEFAULT now(),
            updated_at  TIMESTAMPTZ DEFAULT now()
        )
    """)
    # 建索引：path 唯一索引 + 向量 IVFFlat 索引
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{table}_embedding
        ON {table} USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 50)
    """)
    conn.commit()
    print(f"  → 表 {table} + IVFFlat 索引已创建")

    # 插入数据（UPSERT：path 唯一，存在则更新）
    print("[4/4] 插入向量数据...")
    inserted = 0
    updated = 0
    for i in range(n):
        path = meta["paths"][i]
        kind = meta["kinds"][i]
        summary = meta["summaries"][i]
        category = meta["categories"][i]
        tags = meta["tags"][i]
        text_index = meta["texts"][i]
        context = meta["contexts"][i]
        emb = mat[i].tolist()

        cur.execute(f"""
            INSERT INTO {table} (path, kind, summary, category, tags, text_index, context, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (path) DO UPDATE SET
                kind = EXCLUDED.kind,
                summary = EXCLUDED.summary,
                category = EXCLUDED.category,
                tags = EXCLUDED.tags,
                text_index = EXCLUDED.text_index,
                context = EXCLUDED.context,
                embedding = EXCLUDED.embedding,
                updated_at = now()
            RETURNING (xmax = 0) AS inserted
        """, (path, kind, summary, category, tags, text_index, context, emb))
        is_insert = cur.fetchone()[0]
        if is_insert:
            inserted += 1
        else:
            updated += 1

        if (i + 1) % 500 == 0:
            conn.commit()
            print(f"  → 进度: {i+1}/{n}")

    conn.commit()
    print(f"  → 完成: 新增 {inserted}, 更新 {updated}")

    # 验证
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    total = cur.fetchone()[0]
    print(f"\n[OK] PG 向量表 {table} 共 {total} 条记录")
    conn.close()


if __name__ == "__main__":
    main()
