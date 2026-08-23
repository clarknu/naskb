"""JobManager 异步任务队列测试。"""
import time

from naskb.common.jobs import JobManager


def _wait(jm, job_id, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        j = jm.get(job_id)
        if j and j["status"] in ("completed", "failed"):
            return j
        time.sleep(0.02)
    raise TimeoutError(f"job {job_id} 未在 {timeout}s 内完成: {j}")


def test_submit_and_complete():
    jm = JobManager()

    def work(job, x):
        job["progress"] = 0.5
        job["message"] = "一半"
        return {"x": x * 2}

    jid = jm.submit("test", work, 21)
    j = _wait(jm, jid)
    assert j["status"] == "completed"
    assert j["result"] == {"x": 42}
    assert j["progress"] == 1.0
    assert j["message"] == "一半"
    assert j["started_at"] and j["completed_at"]


def test_failed_job_reports_error():
    jm = JobManager()

    def boom(job):
        raise ValueError("炸了")

    jid = jm.submit("test", boom)
    j = _wait(jm, jid)
    assert j["status"] == "failed"
    assert "ValueError" in j["error"]
    assert "炸了" in j["error"]


def test_get_missing_returns_none():
    jm = JobManager()
    assert jm.get("no-such") is None


def test_list_filter():
    jm = JobManager()

    def ok(job):
        return 1

    jid = jm.submit("a", ok)
    _wait(jm, jid)
    assert len(jm.list()) == 1
    assert len(jm.list(status="completed")) == 1
    assert len(jm.list(status="running")) == 0


def test_shutdown_waits():
    jm = JobManager()

    def slow(job):
        time.sleep(0.2)
        return 1

    jm.submit("a", slow)
    jm.shutdown(wait=True)
    assert len(jm.list()) == 1
