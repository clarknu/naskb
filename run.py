"""NASKB 知识库系统 —— 零安装启动入口。

直接运行：
    python run.py                          # 默认 127.0.0.1:8765，工作区 NASKB_data
    python run.py --host 0.0.0.0 --open    # 局域网可访问 + 自动开浏览器
    python run.py --work D:\\somewhere     # 指定其他工作区

无需 pip install：包导入通过 sys.path 引导（naskb/scripts）；
当前解释器缺平台依赖时自动切换到仓库自带 .venv 重启自身。
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "naskb", "scripts")
if PKG not in sys.path:
    sys.path.insert(0, PKG)
os.environ.setdefault("NASKB_WORK", os.path.join(ROOT, "NASKB_data"))


def _reexec_into_venv() -> None:
    """当前解释器缺 fastapi/uvicorn 时，切到仓库自带 .venv 重启自身。"""
    if importlib.util.find_spec("fastapi") and \
            importlib.util.find_spec("uvicorn"):
        return
    for py in (os.path.join(ROOT, ".venv", "Scripts", "python.exe"),
               os.path.join(ROOT, ".venv", "bin", "python")):
        if os.path.isfile(py):
            print(f"[naskb] 当前解释器缺平台依赖，切换仓库虚拟环境: {py}")
            os.execv(py, [py, os.path.abspath(__file__), *sys.argv[1:]])
    print("[naskb] 未找到 .venv 且当前环境缺少 fastapi/uvicorn。\n"
          "  处理：python -m pip install fastapi uvicorn\n"
          "  或在仓库根创建 .venv 后重试。")
    sys.exit(1)


def main() -> None:
    _reexec_into_venv()
    import argparse

    ap = argparse.ArgumentParser(description="NASKB 知识库系统平台服务 v0.1")
    ap.add_argument("--host", default="127.0.0.1",
                    help="监听地址（局域网用 0.0.0.0）")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--work", default=os.environ["NASKB_WORK"],
                    help="工作区目录（config.toml 所在）")
    ap.add_argument("--open", action="store_true", help="启动后打开浏览器")
    args = ap.parse_args()

    from naskb.common.config import Config
    from naskb.server.app import run

    config = Config.from_work_path(args.work)
    if args.open:
        import threading
        import webbrowser
        url_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
        threading.Timer(1.2, lambda: webbrowser.open(
            f"http://{url_host}:{args.port}/")).start()
    run(config, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
