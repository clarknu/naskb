"""独立运行的压力测试脚本 — 直接写文件避免管道缓冲。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# 重定向 stdout 到文件 + 终端
import io

class TeeWriter:
    def __init__(self, log_path):
        self._file = open(log_path, 'w', encoding='utf-8')
        self._stdout = sys.stdout
    def write(self, s):
        self._file.write(s)
        self._file.flush()
        self._stdout.write(s)
        self._stdout.flush()
    def flush(self):
        self._file.flush()
        self._stdout.flush()

tee = TeeWriter(os.path.join(os.path.dirname(__file__), 'stress_output.log'))
sys.stdout = tee
sys.stderr = tee

# ── 导入测试模块 ──
from test_mcp_stress import TestMCPStress

print('=== Setting up ===', flush=True)
TestMCPStress.setup_class()

t = TestMCPStress()

print('\n=== Phase 1: Full Index ===', flush=True)
t.test_01_full_index()

print('\n=== Phase 2: Verify ===', flush=True)
t.test_02_verify_index()

print('\n=== Phase 3: Query Stress ===', flush=True)
t.test_03_query_stress()

print('\n=== Phase 4: Report ===', flush=True)
t.test_04_final_report()

print('\n=== Teardown ===', flush=True)
TestMCPStress.teardown_class()

tee._file.close()
print('=== ALL DONE ===', flush=True)
