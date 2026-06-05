"""NASKB MCP — MCP Service 形态。

面向持续服务、高并发、大规模并行的异步实现。
- server: FastMCP 服务器主程序
- tools: 16 个 MCP Tool 函数
- async_indexer: 异步索引编排器
- desc_manager: .kbdes 自描述文件管理
- watcher: 文件系统实时监控
- job_queue: 异步任务队列
"""

from .desc_manager import DescManager, KbDesc, MediaInfo
from .job_queue import JobQueue, Job, JobStatus, JobType
from .watcher import FileWatcher
from .async_indexer import AsyncIndexer
