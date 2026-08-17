"""PG 向量检索脚本：通过 pgvector 在 PostgreSQL 中做语义搜索。

用法：
  python pg_search.py "病历 请假条"
  python pg_search.py "珠宝首饰" 10
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "naskb" / "scripts"))

import psycopg2
from pgvector.psycopg2 import register_vector
from naskb.common.config import Config
from naskb.common.embeddings import Embedder


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "病历 请假条"
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    work_path = str(Path(__file__).parent.parent / "NASKB_data")
    config = Config.from_work_path(work_path)

    emb = Embedder(work_path)
    q_vec = emb.encode_one(query)
    emb.close()

    conn = psycopg2.connect(
        host=config.pg_host, port=config.pg_port,
        user=config.pg_user, password=config.pg_password,
        dbname=config.pg_database, connect_timeout=10
    )
    register_vector(conn)
    cur = conn.cursor()

    table = config.pg_vector_table

    # 余弦距离检索（pgvector 1 - cosine_distance = cosine_similarity）
    cur.execute(f"""
        SELECT path, kind, summary, category, tags,
               1 - (embedding <=> %s::vector) AS score
        FROM {table}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (q_vec.tolist(), q_vec.tolist(), top_k))

    rows = cur.fetchall()
    print(f"[PG 向量检索] 查询: {query!r}  top_k={top_k}")
    print()
    for i, (path, kind, summary, category, tags, score) in enumerate(rows, 1):
        summary_short = (summary or "")[:100]
        tags_str = " ".join(tags or [])
        print(f"  {i:2d}. [{score:.3f}] {path}")
        if summary_short:
            print(f"      摘要: {summary_short}")
        if category:
            print(f"      分类: {category}  标签: {tags_str}")
        print()

    print(f"共 {len(rows)} 条结果")
    conn.close()


if __name__ == "__main__":
    main()
