"""CLI 命令面测试（G-08 补全）：28 个 desc 命令注册完整、--help 渲染、关键参数门面、廉价冒烟分支。

说明：CLI 28 命令此前仅被主链路间接覆盖（README/主流程测试），无独立套件（G-08）。
本文件补「命令面完整性」层（对应 tdd-build 类型：正常/错误/边界——不触发重业务）：
  1) 28 命令全部在 click 组中注册且 --help 渲染正常（参数解析层，不执行命令体）；
  2) 关键命令的参数门面（ask --pg / plan-reorganize --apply / sync-vectors --rebuild ┅）；
  3) 错误路径（未知命令 / 缺必需参数 → exit 2）；
  4) 廉价冒烟（空工作区无 [pg] 配置：pg-status / termbase-list 明确提示且 exit 0）。

隔离：NASKB_WORK 指向 pytest tmp 工作区（无 config.toml → Config 默认值；
不读真实 LLM key、不碰真实 PG/工作区）。
"""
import pytest
from click.testing import CliRunner

from naskb.skill.cli import main

# desc 组全部命令（与 cli.py @desc.command 一一对应，README/SKILL 一致 = 28）
EXPECTED_COMMANDS = [
    "adopt", "analyze", "analyze-folder", "analyze-tree", "ask", "check",
    "deep-bench", "deep-eval", "export-clean", "export-repo", "index-vectors",
    "migrate", "move", "orphans", "pg-rebind", "pg-status", "plan-reorganize",
    "scan", "search", "serve", "serve-mcp", "serve-platform", "split",
    "sync-chunks", "sync-status", "sync-vectors", "termbase-add", "termbase-list",
]


@pytest.fixture
def runner(tmp_path):
    """CliRunner + 隔离工作区（NASKB_WORK 指向空 tmp 目录）。"""
    return CliRunner(), str(tmp_path)


def _invoke(runner, argv, work):
    return runner.invoke(main, argv, env={"NASKB_WORK": work})


def test_help_lists_all_28_commands(runner):
    cli, work = runner
    result = _invoke(cli, ["desc", "--help"], work)
    assert result.exit_code == 0, result.output
    for name in EXPECTED_COMMANDS:
        assert name in result.output, f"desc 组缺少命令 {name}"


@pytest.mark.parametrize("name", EXPECTED_COMMANDS)
def test_each_command_help_renders(runner, name):
    cli, work = runner
    result = _invoke(cli, ["desc", name, "--help"], work)
    assert result.exit_code == 0, f"{name} --help 失败: {result.output[:200]}"
    assert "Usage" in result.output
    assert name in result.output


def test_unknown_command_rejected(runner):
    cli, work = runner
    result = _invoke(cli, ["desc", "definitely-not-a-command"], work)
    assert result.exit_code == 2
    assert "No such command" in result.output


def test_missing_required_argument_rejected(runner):
    cli, work = runner
    # analyze 的 path 为必选 argument：缺参 → UsageError (exit 2)，而非崩栈
    result = _invoke(cli, ["desc", "analyze"], work)
    assert result.exit_code == 2
    assert "Usage:" in result.output


@pytest.mark.parametrize("argv,expect_flags", [
    (["ask"], ["--top-k", "--vector", "--pg", "--nas"]),
    (["plan-reorganize"], ["--apply", "--output", "--max-items"]),
    (["sync-vectors"], ["--rebuild", "--nas"]),
    (["sync-chunks"], ["--nas"]),
    (["orphans"], ["--delete"]),
    (["deep-eval"], ["--questions", "--out"]),
    (["export-clean"], ["--zip"]),
    (["serve"], ["--host", "--port", "--root", "--pg"]),
    (["serve-platform"], ["--host", "--port"]),
    (["termbase-add"], []),
])
def test_key_option_surface(runner, argv, expect_flags):
    """抽查关键命令的参数门面（README 承诺的选项必须存在）。"""
    cli, work = runner
    result = _invoke(cli, ["desc"] + argv + ["--help"], work)
    assert result.exit_code == 0, result.output
    for flag in expect_flags:
        assert flag in result.output, f"{argv[0]} --help 缺少 {flag}"


def test_pg_status_without_pg_config(runner):
    """空工作区（无 [pg]）→ 明确提示且 exit 0，不崩溃不挂起。"""
    cli, work = runner
    result = _invoke(cli, ["desc", "pg-status"], work)
    assert result.exit_code == 0, result.output
    assert "未配置 [pg]" in result.output


def test_termbase_list_without_pg_config(runner):
    cli, work = runner
    result = _invoke(cli, ["desc", "termbase-list"], work)
    assert result.exit_code == 0, result.output
    assert "术语表需要 config.toml 配置 [pg]" in result.output


def test_cheap_smoke_termbase_add_help_and_scan_empty_dir(runner, tmp_path):
    """廉价冒烟：空目录 scan（纯确定性操作）→ exit 0 且输出报告头。"""
    cli, work = runner
    empty_dir = tmp_path / "empty-repo"
    empty_dir.mkdir()
    result = _invoke(cli, ["desc", "scan", str(empty_dir)], work)
    # scan 无 .naskb 来源也可运行于本地目录：确定性层不依赖网络/LLM
    assert result.exit_code == 0, result.output
    assert "[naskb]" in result.output or "valid" in result.output.lower()
