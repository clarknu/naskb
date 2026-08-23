"""一次性清理：删除调试/残留测试来源（PG 持久注册表）。"""
import sys

sys.path.insert(0, r"C:\Sync\NASKB\naskb\scripts")
from naskb.common.config import Config  # noqa: E402
from naskb.common.pgstore import PgStore  # noqa: E402

c = Config.from_work_path("NASKB_data")
p = PgStore(c)
sql = """
DELETE FROM nas_local_local_0_uanon.resources
 WHERE source_id IN (SELECT source_id FROM public.sources
                      WHERE alias LIKE 'dbg-src%' OR alias LIKE 't-src%'
                         OR alias LIKE 'smoke-%');
DELETE FROM nas_local_local_0_uanon.folders
 WHERE source_id IN (SELECT source_id FROM public.sources
                      WHERE alias LIKE 'dbg-src%' OR alias LIKE 't-src%'
                         OR alias LIKE 'smoke-%');
DELETE FROM public.sources
 WHERE alias LIKE 'dbg-src%' OR alias LIKE 't-src%' OR alias LIKE 'smoke-%';
"""
with p.connect() as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
print("cleaned, remaining sources:")
with p.connect() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT alias FROM public.sources ORDER BY alias")
        for row in cur.fetchall():
            print(" -", row[0])
