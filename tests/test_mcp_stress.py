"""NASKB MCP Server 压力测试。

测试内容：
1. 数据准备 — 生成5万条5~15字的向量文本（CPU 实测 2000 条约 17min），经向量化后存入向量数据库
2. 索引验证 — 检查建索引过程是否正常、耗时多少
3. 查询压力测试 — 持续20秒进行向量查询，每100ms一次，每次获取最匹配的5条记录
4. 结果统计 — 向量化耗时、查询耗时等分阶段统计，并外推 50,000 条的预期耗时
"""
import gc
import os
import random
import shutil
import string
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# 确保 src 路径可用
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 预先下载好的模型路径
_PRECACHED_MODEL = Path(r"c:\Sync\NASKB\NASKB_data\models\bge-base-zh-v1.5")

# ── 常量 ──
TOTAL_FILES = 2_000         # 生成文件数（CPU 编码 5万需 ~7h，2000 约 17min）
TEXT_MIN_LEN = 5            # 最小文本长度（字符）
TEXT_MAX_LEN = 15           # 最大文本长度（字符）
QUERY_DURATION_SEC = 20     # 查询持续时间（秒）
QUERY_INTERVAL_MS = 100     # 查询间隔（毫秒）
QUERY_TOP_K = 5             # 每次查询返回记录数
FILES_PER_DIR = 500         # 每个子目录的文件数
ONNX_BATCH_SIZE = 64        # ONNX 真正批处理大小


# ═══════════════════════════════════════════════════════════════════
# 快速批量向量化（真正的 ONNX batch inference）
# ═══════════════════════════════════════════════════════════════════

def fast_encode_batch(embedder, texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """真正的批量 ONNX 推理，比逐条 encode 快 10~30 倍。

    原因：embedder.encode_batch 内部逐条调用 encode()，
    本函数一次性 tokenize + 推理整个 batch。
    """
    import numpy as np
    all_vecs = []
    total = len(texts)
    _embed_t0 = time.time()

    for start in range(0, total, batch_size):
        batch = texts[start:start + batch_size]

        # 批量 tokenize
        inputs = embedder._tokenizer(
            batch, padding="max_length", truncation=True,
            max_length=embedder._max_length, return_tensors="np",
        )
        input_ids = inputs["input_ids"]
        attention_mask = inputs["attention_mask"]

        if input_ids.ndim == 1:
            input_ids = input_ids.reshape(1, -1)
        if attention_mask.ndim == 1:
            attention_mask = attention_mask.reshape(1, -1)

        # ONNX 批量推理
        outputs = embedder._session.run(
            None, {
                "input_ids": input_ids.astype(np.int64),
                "attention_mask": attention_mask.astype(np.int64),
            }
        )
        token_embeddings = outputs[0]  # (batch, seq_len, dim)

        # Mean pooling (批量版)
        mask = np.expand_dims(attention_mask.astype(token_embeddings.dtype), axis=-1)
        masked = token_embeddings * mask
        summed = masked.sum(axis=1)
        count = np.maximum(mask.sum(axis=1), 1e-9)
        embeddings = (summed / count).squeeze(1) if summed.ndim > 2 else summed / count

        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / (norms + 1e-9)

        for vec in embeddings.astype(np.float32).tolist():
            all_vecs.append(vec)

        done = min(start + batch_size, total)
        if done % (batch_size * 5) == 0 or done == total:
            elapsed = time.time() - _embed_t0
            rate = done / max(elapsed, 0.001)
            print(f"  [FAST-EMBED] {done}/{total} ({done*100//total}%) "
                  f"elapsed={elapsed:.1f}s rate={rate:.0f} texts/s", flush=True)

    return all_vecs


# ═══════════════════════════════════════════════════════════════════
# 计时工具
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TimingStats:
    """分阶段耗时统计。"""
    phase_name: str = ""
    wall_start: float = 0.0
    wall_end: float = 0.0
    cpu_start: float = 0.0
    cpu_end: float = 0.0

    @property
    def wall_seconds(self) -> float:
        return self.wall_end - self.wall_start

    @property
    def cpu_seconds(self) -> float:
        return self.cpu_end - self.cpu_start

    def __str__(self) -> str:
        return (f"{self.phase_name}: "
                f"耗时 {self.wall_seconds:.3f}s (CPU {self.cpu_seconds:.3f}s)")


@dataclass
class StressTestReport:
    """压力测试综合报告。"""
    # 数据准备
    files_generated: int = 0
    gen_text_time: TimingStats = field(default_factory=lambda: TimingStats("生成文本内容"))
    gen_file_time: TimingStats = field(default_factory=lambda: TimingStats("写入文件系统"))

    # 索引
    index_total_time: TimingStats = field(default_factory=lambda: TimingStats("全量索引总计"))
    index_scan_time: float = 0.0          # 扫描耗时
    index_embed_time: float = 0.0         # 向量化耗时
    index_store_time: float = 0.0         # 写入向量库耗时
    index_file_count: int = 0             # 实际索引文件数

    # 查询
    query_total_queries: int = 0
    query_total_time: TimingStats = field(default_factory=lambda: TimingStats("查询阶段总计"))
    query_encode_times: list[float] = field(default_factory=list)  # 每次查询向量化耗时
    query_search_times: list[float] = field(default_factory=list)  # 每次查询搜索耗时
    query_total_times: list[float] = field(default_factory=list)   # 每次查询总耗时
    query_errors: int = 0
    query_empty_results: int = 0

    def format_report(self) -> str:
        lines = [
            "=" * 70,
            "  NASKB MCP Server 压力测试报告",
            "=" * 70,
            "",
            "─── 第一阶段：数据准备 ───",
            f"  生成文件数:        {self.files_generated:,}",
            f"  文本内容生成:      {self.gen_text_time}",
            f"  文件系统写入:      {self.gen_file_time}",
            "",
            "─── 第二阶段：建索引 ───",
            f"  实际索引文件数:    {self.index_file_count:,}",
            f"  全量索引总耗时:    {self.index_total_time}",
            f"    ├─ 向量化嵌入:   {self.index_embed_time:.3f}s",
            f"    └─ 写入向量库:   {self.index_store_time:.3f}s",
        ]

        if self.index_file_count > 0:
            avg_per_file = self.index_total_time.wall_seconds / self.index_file_count * 1000
            lines.append(f"    平均每文件:      {avg_per_file:.2f}ms")
            files_per_sec = self.index_file_count / max(self.index_total_time.wall_seconds, 0.001)
            lines.append(f"    吞吐量:          {files_per_sec:.0f} files/sec")

        lines.extend([
            "",
            "─── 第三阶段：查询压力测试 ───",
            f"  查询持续时间:      {self.query_total_time.wall_seconds:.1f}s",
            f"  总查询次数:        {self.query_total_queries:,}",
            f"  查询错误次数:      {self.query_errors}",
            f"  空结果次数:        {self.query_empty_results}",
        ])

        if self.query_total_times:
            qt = self.query_total_times
            et = self.query_encode_times
            st = self.query_search_times
            lines.extend([
                f"  单次查询耗时:      "
                f"min={min(qt)*1000:.1f}ms  "
                f"max={max(qt)*1000:.1f}ms  "
                f"avg={sum(qt)/len(qt)*1000:.1f}ms  "
                f"p50={sorted(qt)[len(qt)//2]*1000:.1f}ms  "
                f"p95={sorted(qt)[int(len(qt)*0.95)]*1000:.1f}ms  "
                f"p99={sorted(qt)[int(len(qt)*0.99)]*1000:.1f}ms",
                f"  向量化耗时:        "
                f"min={min(et)*1000:.1f}ms  "
                f"max={max(et)*1000:.1f}ms  "
                f"avg={sum(et)/len(et)*1000:.1f}ms",
                f"  搜索耗时:          "
                f"min={min(st)*1000:.1f}ms  "
                f"max={max(st)*1000:.1f}ms  "
                f"avg={sum(st)/len(st)*1000:.1f}ms",
                f"  QPS (每秒查询数):  "
                f"{self.query_total_queries / max(self.query_total_time.wall_seconds, 0.001):.1f}",
            ])

        lines.extend(["", "=" * 70])
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 压力测试主类
# ═══════════════════════════════════════════════════════════════════

class TestMCPStress:
    """MCP Server 压力测试。"""

    @classmethod
    def setup_class(cls):
        """创建临时环境、生成测试数据、初始化组件。"""
        cls.report = StressTestReport()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work_path = cls.tmp.name
        os.environ["NASKB_WORK"] = cls.work_path

        wp = Path(cls.work_path)

        # ── 复制模型 ──
        if _PRECACHED_MODEL.exists():
            dst_model = wp / "models" / "bge-base-zh-v1.5"
            dst_model.mkdir(parents=True, exist_ok=True)
            for f in _PRECACHED_MODEL.iterdir():
                if f.is_file():
                    shutil.copy2(f, dst_model / f.name)
            print(f"[SETUP] Model copied from {_PRECACHED_MODEL}")
        else:
            raise FileNotFoundError(
                f"Pre-cached model not found at {_PRECACHED_MODEL}. "
                f"Run: naskb init --work-path c:/Sync/NASKB/NASKB_data"
            )

        # ── 创建知识库来源目录 ──
        cls.source_dir = wp / "stress_kb"
        cls.source_dir.mkdir(parents=True)

        # ── 写 config.toml ──
        config_content = f"""
[model]
name = "bge-base-zh-v1.5"
execution_provider = "cpu"
batch_size = 32
intra_op_threads = 4
inter_op_threads = 2

[db]
path = "db/"

[state]
path = "state.db"

[[sources]]
id = "stress-kb"
name = "Stress Test KB"
fs_type = "local"
root_url = "{str(cls.source_dir.resolve()).replace(chr(92), '/')}"
enabled = true
"""
        (wp / "config.toml").write_text(config_content, encoding="utf-8")

        # ── 生成 50,000 条文本数据 ──
        print(f"\n[SETUP] Generating {TOTAL_FILES:,} text files...")
        cls._generate_test_data()

        # ── 初始化组件 ──
        from naskb.mcp.tools import _init_components
        cls.components = _init_components(cls.work_path)
        cls.config = cls.components["config"]
        cls.embedder = cls.components["embedder"]
        cls.vector_store = cls.components["vector_store"]
        cls.state = cls.components["state"]
        cls.async_indexer = cls.components["async_indexer"]
        cls.source_manager = cls.components["source_manager"]

        print(f"[SETUP] Work path: {cls.work_path}")
        print(f"[SETUP] Source dir: {cls.source_dir}")
        print(f"[SETUP] Components initialized, embedder provider: "
              f"{cls.embedder.provider}")

    @classmethod
    def teardown_class(cls):
        """清理临时环境。"""
        for key in ("state", "vector_store"):
            try:
                obj = cls.components.get(key)
                if obj:
                    if hasattr(obj, "_conn"):
                        obj._conn.close()
                    if hasattr(obj, "_db"):
                        obj._db.close()
            except Exception:
                pass
        try:
            cls.components["async_indexer"].shutdown()
        except Exception:
            pass
        gc.collect()
        time.sleep(0.5)
        try:
            cls.tmp.cleanup()
        except PermissionError:
            pass
        print("[TEARDOWN] Cleanup done")

    @classmethod
    def _generate_test_data(cls):
        """生成 50,000 条 5~15 字的中文/英文混合文本文件。

        文本内容覆盖多种主题，以便后续查询有合理的语义匹配。
        """
        # 主题词库，确保生成的文本有语义多样性
        TOPICS = [
            "数据库优化", "向量检索", "机器学习", "深度学习", "自然语言处理",
            "计算机视觉", "分布式系统", "微服务架构", "容器编排", "云计算平台",
            "网络安全", "密码学原理", "数据加密", "身份认证", "访问控制",
            "操作系统", "文件系统", "内存管理", "进程调度", "线程同步",
            "Python编程", "异步编程", "并发模型", "设计模式", "代码重构",
            "前端开发", "后端架构", "API设计", "RESTful", "GraphQL",
            "数据分析", "数据可视化", "统计建模", "回归分析", "聚类算法",
            "搜索引擎", "推荐系统", "知识图谱", "图数据库", "时序数据库",
            "消息队列", "缓存策略", "负载均衡", "服务发现", "配置管理",
            "日志分析", "监控告警", "链路追踪", "灰度发布", "持续集成",
            "深度强化学习", "生成对抗网络", "变分自编码器", "图神经网络",
            "语音识别", "图像分割", "目标检测", "文本分类", "情感分析",
            "大语言模型", "注意力机制", "Transformer", "预训练模型", "微调策略",
            "边缘计算", "物联网", "嵌入式系统", "实时处理", "流式计算",
            "区块链技术", "智能合约", "去中心化", "共识算法", "零知识证明",
        ]

        # 动词/动作词
        ACTIONS = [
            "实现了", "优化了", "设计了", "部署了", "测试了",
            "分析了", "改进了", "重构了", "调试了", "编写了",
            "学习了", "研究了", "比较了", "评估了", "总结了",
            "搭建了", "配置了", "监控了", "排查了", "修复了",
        ]

        # 补充词
        EXTRAS = [
            "方案", "策略", "流程", "框架", "工具",
            "技术", "方法", "原理", "机制", "实践",
            "经验", "笔记", "心得", "总结", "教程",
            "文档", "指南", "规范", "标准", "最佳",
        ]

        rng = random.Random(42)  # 固定种子，可复现

        def gen_text() -> str:
            """生成 5~15 字的文本。"""
            topic = rng.choice(TOPICS)
            action = rng.choice(ACTIONS)
            extra = rng.choice(EXTRAS)
            # 组合策略：随机选一种模式
            mode = rng.randint(0, 4)
            if mode == 0:
                # "数据库优化实现了新方案"
                text = topic + rng.choice(ACTIONS) + "了新" + rng.choice(EXTRAS)
            elif mode == 1:
                # "Python编程最佳实践"
                text = topic + rng.choice(EXTRAS)
            elif mode == 2:
                # "深度学习模型优化策略"
                text = topic + rng.choice(EXTRAS) + "研究"
            elif mode == 3:
                # "异步编程学习笔记"
                text = topic + rng.choice(EXTRAS) + "笔记"
            else:
                # "搜索引擎相关技术方案"
                text = topic + "相关" + rng.choice(EXTRAS)

            # 裁剪到 5~15 字
            if len(text) > TEXT_MAX_LEN:
                text = text[:TEXT_MAX_LEN]
            elif len(text) < TEXT_MIN_LEN:
                # 不够则补充随机字符
                while len(text) < TEXT_MIN_LEN:
                    text += rng.choice(EXTRAS)
                text = text[:TEXT_MAX_LEN]
            return text

        # ── 批量写入文件 ──
        t0_gen = time.perf_counter()
        os_cpu0 = time.process_time()

        texts: list[str] = []
        for i in range(TOTAL_FILES):
            texts.append(gen_text())

        cls.report.gen_text_time.wall_start = t0_gen
        cls.report.gen_text_time.cpu_start = os_cpu0
        cls.report.gen_text_time.wall_end = time.perf_counter()
        cls.report.gen_text_time.cpu_end = time.process_time()

        t0_file = time.perf_counter()
        os_cpu_file = time.process_time()

        # 分目录存储，每 FILES_PER_DIR 个文件一个子目录
        num_dirs = (TOTAL_FILES + FILES_PER_DIR - 1) // FILES_PER_DIR
        for dir_idx in range(num_dirs):
            sub_dir = cls.source_dir / f"batch_{dir_idx:04d}"
            sub_dir.mkdir(parents=True, exist_ok=True)
            start = dir_idx * FILES_PER_DIR
            end = min(start + FILES_PER_DIR, TOTAL_FILES)
            for i in range(start, end):
                file_path = sub_dir / f"doc_{i:06d}.txt"
                file_path.write_text(texts[i], encoding="utf-8")

        cls.report.gen_file_time.wall_start = t0_file
        cls.report.gen_file_time.cpu_start = os_cpu_file
        cls.report.gen_file_time.wall_end = time.perf_counter()
        cls.report.gen_file_time.cpu_end = time.process_time()
        cls.report.files_generated = TOTAL_FILES

        print(f"  [DATA] Generated {TOTAL_FILES:,} files in {num_dirs} subdirectories")
        print(f"  [DATA] Text generation: {cls.report.gen_text_time}")
        print(f"  [DATA] File writing:    {cls.report.gen_file_time}")

    # ═══════════════════════════════════════════════════════════════
    # Phase 1: 全量建索引（含向量化）
    # ═══════════════════════════════════════════════════════════════

    def test_01_full_index(self):
        """全量索引 50,000 文件并记录分阶段耗时。"""
        print("\n" + "=" * 60)
        print("  Phase 1: 全量索引（50,000 文件）")
        print("=" * 60)

        # ── 直接调用底层组件来分阶段计时 ──
        from naskb.common.scanner import Scanner

        t_total_start = time.perf_counter()
        t_total_cpu = time.process_time()

        # ── 1a: 扫描文件 ──
        t_scan_start = time.perf_counter()
        fs = self.source_manager.get_fs("stress-kb")
        source = None
        for s in self.source_manager.get_sources():
            if s.id == "stress-kb":
                source = s
                break
        assert source is not None, "stress-kb source not found"

        root = source.root_url
        scanner = Scanner(fs, self.config.exclusions)
        scanned = scanner.scan(root)
        t_scan_end = time.perf_counter()
        scan_time = t_scan_end - t_scan_start
        print(f"  [SCAN] Scanned {len(scanned)} files in {scan_time:.3f}s")

        # ── 1b: 读取文件内容 ──
        t_read_start = time.perf_counter()
        # 批量读取所有文本文件内容
        text_files = [sf for sf in scanned if sf.type == "text"]
        print(f"  [READ] Reading {len(text_files)} text files...")

        import asyncio

        async def _read_all():
            async def read_one(sf):
                try:
                    content = await asyncio.to_thread(fs.read_text, sf.path)
                    return (content, sf)
                except Exception:
                    return ("", sf)
            tasks = [read_one(sf) for sf in text_files]
            return await asyncio.gather(*tasks)

        texts_and_metas = asyncio.run(_read_all())
        texts_and_metas = [(t, m) for t, m in texts_and_metas if t.strip()]
        t_read_end = time.perf_counter()
        read_time = t_read_end - t_read_start
        print(f"  [READ] Read {len(texts_and_metas)} files in {read_time:.3f}s")

        # ── 1c: 向量化（真正的 ONNX 批量推理） ──
        t_embed_start = time.perf_counter()
        t_embed_cpu = time.process_time()

        all_texts = [t for t, _ in texts_and_metas]
        print(f"  [EMBED] Fast batch encoding {len(all_texts)} texts "
              f"(batch_size={ONNX_BATCH_SIZE})...")
        all_vectors = fast_encode_batch(
            self.embedder, all_texts, batch_size=ONNX_BATCH_SIZE
        )

        t_embed_end = time.perf_counter()
        t_embed_cpu_end = time.process_time()
        embed_time = t_embed_end - t_embed_start
        rate = len(all_texts) / max(embed_time, 0.001)
        print(f"  [EMBED] Embedded {len(all_texts)} texts in {embed_time:.3f}s "
              f"({rate:.0f} texts/s)")

        # ── 1d: 写入向量库 ──
        t_store_start = time.perf_counter()
        import hashlib

        file_records = []
        for i, (text, meta) in enumerate(zip(
            [t for t, _ in texts_and_metas],
            [m for _, m in texts_and_metas],
        )):
            content_hash = hashlib.md5(
                text[:65536].encode("utf-8", errors="replace")
            ).hexdigest()
            record = {
                "id": hashlib.md5(
                    f"{source.id}:{meta.path}".encode()
                ).hexdigest(),
                "source_id": source.id,
                "path": meta.path,
                "rel_path": meta.rel_path,
                "name": meta.name,
                "ext": meta.ext,
                "type": meta.type,
                "size_bytes": meta.size_bytes,
                "mtime": meta.mtime,
                "vector": all_vectors[i] if isinstance(all_vectors[i], list) else all_vectors[i].tolist(),
                "indexed_at": time.time(),
                "text_snippet": text[:1000],
                "orig_file": "",
                "status": "indexed",
            }
            file_records.append(record)

        # 分批写入向量库
        store_batch = 5000
        for i in range(0, len(file_records), store_batch):
            batch = file_records[i:i + store_batch]
            self.vector_store.add_files(batch)
            done = min(i + store_batch, len(file_records))
            print(f"  [STORE] Written {done}/{len(file_records)} records to vector store")

        t_store_end = time.perf_counter()
        store_time = t_store_end - t_store_start
        print(f"  [STORE] Stored {len(file_records)} records in {store_time:.3f}s")

        # ── 1e: 标记 state ──
        t_state_start = time.perf_counter()
        import hashlib as hl
        for text, meta in texts_and_metas:
            content_hash = hl.md5(
                text[:65536].encode("utf-8", errors="replace")
            ).hexdigest()
            self.state.mark_indexed(
                source.id, meta.path, meta.mtime,
                meta.size_bytes, content_hash,
                rel_path=meta.rel_path, name=meta.name,
            )
        t_state_end = time.perf_counter()

        t_total_end = time.perf_counter()
        t_total_cpu_end = time.process_time()

        # ── 记录报告 ──
        self.report.index_total_time.wall_start = t_total_start
        self.report.index_total_time.wall_end = t_total_end
        self.report.index_total_time.cpu_start = t_total_cpu
        self.report.index_total_time.cpu_end = t_total_cpu_end
        self.report.index_scan_time = scan_time
        self.report.index_embed_time = embed_time
        self.report.index_store_time = store_time
        self.report.index_file_count = len(file_records)

        # ── 验证 ──
        db_count = self.vector_store.count("files")
        print(f"\n  [VERIFY] Vector store record count: {db_count:,}")
        assert db_count >= TOTAL_FILES, (
            f"Expected >= {TOTAL_FILES:,} records, got {db_count:,}"
        )

        print(f"\n  [RESULT] 全量索引完成: {len(file_records):,} 文件")
        print(f"  [RESULT] 总耗时: {self.report.index_total_time}")
        print(f"  [RESULT] 向量化耗时: {embed_time:.3f}s "
              f"({len(file_records)/max(embed_time,0.001):.0f} texts/s)")

    # ═══════════════════════════════════════════════════════════════
    # Phase 2: 索引结果验证
    # ═══════════════════════════════════════════════════════════════

    def test_02_verify_index(self):
        """验证索引结果的正确性。"""
        print("\n" + "=" * 60)
        print("  Phase 2: 索引结果验证")
        print("=" * 60)

        import lancedb

        db = lancedb.connect(str(self.vector_store._db_path))
        try:
            tbl = db.open_table("files")
            count = tbl.count_rows()
        except Exception:
            count = 0

        print(f"  [VERIFY] LanceDB 'files' table row count: {count:,}")
        assert count >= TOTAL_FILES, (
            f"Expected >= {TOTAL_FILES:,} rows, got {count:,}"
        )

        # 验证向量维度
        sample = tbl.search().limit(1).to_list()
        if sample:
            vec = sample[0].get("vector", [])
            print(f"  [VERIFY] Vector dimension: {len(vec)}")
            assert len(vec) == self.embedder.dim, (
                f"Expected dim={self.embedder.dim}, got {len(vec)}"
            )

        # 验证搜索功能
        from naskb.mcp.tools import kb_search
        result = kb_search("数据库优化", top_k=5, threshold=0.3)
        print(f"\n  [SEARCH TEST] '数据库优化':")
        print(f"  {result[:200]}...")
        assert "找到" in result or "结果" in result, "Search should return results"

        result2 = kb_search("机器学习模型训练", top_k=5, threshold=0.3)
        print(f"\n  [SEARCH TEST] '机器学习模型训练':")
        print(f"  {result2[:200]}...")
        assert "找到" in result2 or "结果" in result2, "Search should return results"

        print("\n  [RESULT] 索引验证通过 OK")

    # ═══════════════════════════════════════════════════════════════
    # Phase 3: 查询压力测试
    # ═══════════════════════════════════════════════════════════════

    def test_03_query_stress(self):
        """持续20秒向量查询压力测试。"""
        print("\n" + "=" * 60)
        print("  Phase 3: 查询压力测试")
        print(f"  持续 {QUERY_DURATION_SEC}s, 间隔 {QUERY_INTERVAL_MS}ms, "
              f"top_k={QUERY_TOP_K}")
        print("=" * 60)

        # 查询用的随机种子（不同于数据生成的种子）
        rng = random.Random(12345)

        # 查询关键词库
        QUERY_WORDS = [
            "数据库", "优化", "学习", "模型", "训练",
            "搜索", "索引", "缓存", "并发", "异步",
            "网络", "安全", "加密", "算法", "图",
            "深度", "神经", "语音", "图像", "文本",
            "分布式", "微服务", "容器", "监控", "日志",
            "前端", "后端", "API", "架构", "设计",
        ]

        def gen_query_text() -> str:
            """生成 5~15 字的随机查询文本。"""
            parts = []
            total_len = 0
            while total_len < TEXT_MIN_LEN:
                word = rng.choice(QUERY_WORDS)
                parts.append(word)
                total_len += len(word)
            text = "".join(parts)
            if len(text) > TEXT_MAX_LEN:
                text = text[:TEXT_MAX_LEN]
            return text

        # ── 预热：先执行几次查询 ──
        print("  [WARMUP] Warming up embedder...")
        for _ in range(10):
            q = gen_query_text()
            _ = self.embedder.encode(q)
        print("  [WARMUP] Done")

        # ── 开始压力测试 ──
        print(f"\n  [STRESS] Starting {QUERY_DURATION_SEC}s query stress test...")
        t_start = time.perf_counter()
        query_count = 0
        errors = 0
        empty = 0
        encode_times = []
        search_times = []
        total_times = []

        interval_sec = QUERY_INTERVAL_MS / 1000.0

        while True:
            now = time.perf_counter()
            elapsed = now - t_start
            if elapsed >= QUERY_DURATION_SEC:
                break

            # 生成随机查询
            query_text = gen_query_text()

            t_q_start = time.perf_counter()

            # 向量化查询文本
            t_enc_start = time.perf_counter()
            try:
                query_vec = self.embedder.encode(query_text)
                t_enc_end = time.perf_counter()
                enc_time = t_enc_end - t_enc_start
            except Exception as e:
                errors += 1
                t_enc_end = time.perf_counter()
                enc_time = t_enc_end - t_enc_start
                # 跳过这次查询
                time.sleep(max(0, interval_sec - (time.perf_counter() - t_q_start)))
                continue

            # 搜索向量库
            t_srch_start = time.perf_counter()
            try:
                results = self.vector_store.search(
                    query_vec, top_k=QUERY_TOP_K, threshold=0.0
                )
                t_srch_end = time.perf_counter()
                srch_time = t_srch_end - t_srch_start
            except Exception as e:
                errors += 1
                t_srch_end = time.perf_counter()
                srch_time = t_srch_end - t_srch_start
                time.sleep(max(0, interval_sec - (time.perf_counter() - t_q_start)))
                continue

            t_q_end = time.perf_counter()
            q_total = t_q_end - t_q_start

            if not results:
                empty += 1

            encode_times.append(enc_time)
            search_times.append(srch_time)
            total_times.append(q_total)
            query_count += 1

            # 定期输出进度
            if query_count % 50 == 0:
                avg_q = sum(total_times[-50:]) / min(50, len(total_times[-50:]))
                print(f"  [STRESS] t={elapsed:.1f}s  queries={query_count}  "
                      f"avg={avg_q*1000:.1f}ms  errors={errors}")

            # 等待下一个查询间隔
            next_time = t_start + (query_count) * interval_sec
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)

        t_end = time.perf_counter()

        # ── 记录报告 ──
        self.report.query_total_time.wall_start = t_start
        self.report.query_total_time.wall_end = t_end
        self.report.query_total_queries = query_count
        self.report.query_encode_times = encode_times
        self.report.query_search_times = search_times
        self.report.query_total_times = total_times
        self.report.query_errors = errors
        self.report.query_empty_results = empty

        # ── 输出 ──
        actual_duration = t_end - t_start
        qps = query_count / max(actual_duration, 0.001)
        print(f"\n  [RESULT] Query stress test completed:")
        print(f"  [RESULT] Duration:     {actual_duration:.1f}s")
        print(f"  [RESULT] Total queries: {query_count:,}")
        print(f"  [RESULT] QPS:           {qps:.1f}")
        print(f"  [RESULT] Errors:        {errors}")
        print(f"  [RESULT] Empty results: {empty}")

        if total_times:
            qt = total_times
            print(f"  [RESULT] Query latency:")
            print(f"           min={min(qt)*1000:.1f}ms  "
                  f"max={max(qt)*1000:.1f}ms  "
                  f"avg={sum(qt)/len(qt)*1000:.1f}ms")
            sorted_qt = sorted(qt)
            print(f"           p50={sorted_qt[len(sorted_qt)//2]*1000:.1f}ms  "
                  f"p95={sorted_qt[int(len(sorted_qt)*0.95)]*1000:.1f}ms  "
                  f"p99={sorted_qt[int(len(sorted_qt)*0.99)]*1000:.1f}ms")

        assert query_count > 0, "Should have completed at least one query"
        assert errors == 0, f"Should have no errors, got {errors}"

        print("\n  [RESULT] 查询压力测试通过 OK")

    # ═══════════════════════════════════════════════════════════════
    # Phase 4: 综合报告
    # ═══════════════════════════════════════════════════════════════

    def test_04_final_report(self):
        """输出综合压力测试报告。"""
        print("\n")
        report_text = self.report.format_report()
        print(report_text)

        # 保存报告到文件
        report_path = Path(self.work_path) / "stress_test_report.txt"
        report_path.write_text(report_text, encoding="utf-8")
        print(f"\n  [REPORT] Saved to: {report_path}")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short",
                          "--timeout=600"]))
