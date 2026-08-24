"""
架构契约门禁（pytest 包装）——规范：_shared/arch-contract-spec.md §10

包装 skill 分发的运行器（node run.mjs）：
  探针（scripts/probes/probe_naskb.py）→ facts.json → run.mjs --contract arch-contract.js
断言：退出码 0（mechanical 全过 + 未到期债务豁免）。

运行：python -m pytest tests/test_arch_contract.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / ".agents" / "skills" / "sfds" / "_shared" / "arch-contract" / "run.mjs"
CONTRACT = REPO / "design" / "05-backend-architecture" / "data" / "arch-contract.js"
PROBE = REPO / "scripts" / "probes" / "probe_naskb.py"
FACTS = REPO / "scripts" / "probes" / "out" / "facts.json"
REPORT = REPO / "design" / "review" / "arch-contract" / "latest.json"


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=600,
                          cwd=str(REPO), encoding="utf-8", errors="replace")


def _probe() -> None:
    python = sys.executable or "python"
    r = _run([python, str(PROBE)])
    assert r.returncode == 0, f"探针失败：{r.stdout}\n{r.stderr}"


def _runner() -> subprocess.CompletedProcess:
    return _run(["node", str(RUNNER),
                 "--contract", str(CONTRACT),
                 "--facts", str(FACTS),
                 "--report", str(REPORT)])


def test_arch_contract_mechanical_passes() -> None:
    """架构契约机械校验：退出码 0（mechanical 全过；heuristic WARN 与 knownDebts 豁免允许）。"""
    _probe()
    r = _runner()
    assert r.returncode != 2, f"基础设施失败：{r.stdout}\n{r.stderr}"
    name = r.returncode == 0
    detail = ""
    if REPORT.exists():
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        detail = f" summary={data.get('summary')}"
        violations = [i for i in data.get("issues", []) if i.get("enforcement") == "mechanical" and not i.get("debtMatched")]
        assert name, f"未豁免 mechanical 违规：\n" + "\n".join(
            f"  {i['ruleId']} @ {i.get('ref_path')}: {i.get('detail')}" for i in violations
        ) + "\n" + r.stdout + detail
    else:
        assert name, f"运行失败且无报告：{r.stdout}\n{r.stderr}"


def test_arch_contract_report_exists() -> None:
    """契约运行报告落盘（review D11 / 发布门禁第 9 项消费）。"""
    assert REPORT.exists(), "缺少运行报告 design/review/arch-contract/latest.json"
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    assert data["summary"]["producer"] == "backend-architecture-design"
