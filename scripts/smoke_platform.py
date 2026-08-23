"""真实服务冒烟：uvicorn 起平台服务，验证注册→扫描→浏览→Range 下载。"""
import io
import json
import os
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, r"C:\Sync\NASKB\naskb\scripts")

BASE = "http://127.0.0.1:8899"


def req(method, path, body=None, headers=None, raw=False):
    import urllib.error
    r = urllib.request.Request(BASE + path, method=method,
                               headers=headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, data=data, timeout=30) as resp:
            payload = resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, hdrs, payload
    except urllib.error.HTTPError as e:      # 304 等也按响应处理
        hdrs = {k.lower(): v for k, v in e.headers.items()}
        return e.code, hdrs, e.read()


def main():
    # 1. 服务健康
    st, _, body = req("GET", "/api/config/public")
    assert st == 200 and json.loads(body)["version"], body
    print("1. config/public OK:", json.loads(body))

    # 2. 注册本地源
    src_dir = Path(os.environ["TEMP"]) / ("naskb-smoke-" + uuid.uuid4().hex[:6])
    (src_dir / "sub").mkdir(parents=True)
    (src_dir / "sub" / "hello.txt").write_text("冒烟测试内容", encoding="utf-8")
    big = src_dir / "blob.bin"
    big.write_bytes(os.urandom(256 * 1024))
    st, _, body = req("POST", "/api/sources", body={
        "alias": "smoke-" + uuid.uuid4().hex[:6], "protocol": "local",
        "root_path": str(src_dir), "access_mode": "ro"})
    assert st == 200, body
    sid = json.loads(body)["source"]["source_id"]
    print("2. source registered:", sid)

    # 3. 扫描
    st, _, body = req("POST", f"/api/sources/{sid}/scan?hash=true")
    assert st == 200, body
    job_id = json.loads(body)["job_id"]
    for _ in range(60):
        st, _, body = req("GET", f"/api/jobs/{job_id}")
        j = json.loads(body)
        if j["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    assert j["status"] == "completed", j
    print("3. scan completed:", j["result"])

    # 4. 浏览
    st, _, body = req("GET", f"/api/tree?src={sid}&dir=sub")
    tree = json.loads(body)
    assert tree["files"] and tree["files"][0]["name"] == "hello.txt"
    rid_txt = tree["files"][0]["resource_id"]
    print("4. tree OK:", tree["files"][0])

    # 5. 预览（文本）
    st, _, body = req("GET", f"/api/files/{rid_txt}/preview?src={sid}")
    p = json.loads(body)
    assert p["viewable"] == "text" and "冒烟测试" in p["content"], p
    print("5. text preview OK")

    # 6. 大文件 Range 下载（206）
    st, _, body = req("GET", f"/api/tree?src={sid}&dir=")
    rid_bin = next(f["resource_id"] for f in json.loads(body)["files"]
                   if f["name"] == "blob.bin")
    st, headers, payload = req(
        "GET", f"/api/files/{rid_bin}/download?src={sid}",
        headers={"Range": "bytes=0-1023"})
    assert st == 206 and len(payload) == 1024, (st, len(payload))
    assert headers["content-range"].startswith("bytes 0-1023/262144"), headers
    print("6. range 206 OK:", headers["content-range"])

    # 7. ETag 304
    etag = headers["etag"]
    st, _, _ = req("GET", f"/api/files/{rid_bin}/download?src={sid}",
                   headers={"If-None-Match": etag})
    assert st == 304, st
    print("7. etag 304 OK")

    # 8. 清理
    st, _, _ = req("DELETE", f"/api/sources/{sid}?purge=true")
    assert st == 200
    print("8. cleanup OK —— 冒烟全链路通过")


if __name__ == "__main__":
    main()
