from __future__ import annotations

import json
import math
import random
import shutil
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "NASKB_data" / "models" / "bge-base-zh-v1.5"
MODEL_PATH = MODEL_DIR / "model.onnx"
OUTPUT_DIR = ROOT / "scripts" / "benchmarks" / "output"
LANCEDB_DIR = OUTPUT_DIR / "lancedb_tmp"


SAMPLE_TEXTS = [
    "请总结这个项目当前的技术路线与风险。",
    "AMD GPU 加速 ONNX Runtime 在 Windows 上的兼容性如何？",
    "向量数据库的检索延迟主要受哪些因素影响？",
    "对于中文知识库，bge-base 和 bge-large 的差异是什么？",
    "如果数据规模增长到十万级别，索引策略应该怎么调整？",
    "请从 CPU、GPU 和 NPU 三个角度分析本地部署的可行性。",
    "LanceDB 与 Qdrant 在嵌入式部署场景下有什么差异？",
    "如何判断 ONNX Runtime 是否真的在使用 DirectML 而不是 CPU 回退？",
    "批量嵌入时 batch size 对吞吐量和显存压力有什么影响？",
    "请解释为什么向量检索不一定能从 NPU 获得收益。",
]


@dataclass
class TimingStats:
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float


def compute_timing_stats(samples: list[float]) -> TimingStats:
    if not samples:
        return TimingStats(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    ordered = sorted(samples)

    def percentile(p: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        index = (len(ordered) - 1) * p
        low = math.floor(index)
        high = math.ceil(index)
        if low == high:
            return ordered[low]
        weight = index - low
        return ordered[low] * (1 - weight) + ordered[high] * weight

    return TimingStats(
        count=len(samples),
        mean_ms=round(statistics.mean(samples), 3),
        p50_ms=round(percentile(0.50), 3),
        p95_ms=round(percentile(0.95), 3),
        min_ms=round(min(samples), 3),
        max_ms=round(max(samples), 3),
    )


def probe_environment() -> dict[str, Any]:
    import importlib.metadata as md
    import importlib.util as util
    import platform
    import sys

    info: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "packages": {},
        "onnxruntime": {},
    }

    package_names = [
        "onnxruntime",
        "onnxruntime-directml",
        "lancedb",
        "pyarrow",
        "tokenizers",
        "transformers",
        "torch",
        "faiss-cpu",
        "hnswlib",
        "qdrant-client",
    ]
    for name in package_names:
        try:
            info["packages"][name] = md.version(name)
        except md.PackageNotFoundError:
            info["packages"][name] = None

    try:
        import onnxruntime as ort

        info["onnxruntime"] = {
            "module_path": str(Path(ort.__file__).resolve()),
            "available_providers": ort.get_available_providers(),
        }
    except Exception as exc:
        info["onnxruntime"] = {"error": repr(exc)}

    info["optional_modules"] = {
        name: bool(util.find_spec(name))
        for name in ["faiss", "hnswlib", "qdrant_client"]
    }
    return info


def load_tokenizer(model_dir: Path):
    try:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
        return tokenizer, "transformers"
    except Exception:
        from tokenizers import Tokenizer

        raw = Tokenizer.from_file(str(model_dir / "tokenizer.json"))

        class SimpleTokenizer:
            def __init__(self, tok):
                self._tok = tok
                self.pad_token_id = tok.token_to_id("[PAD]") or 0
                self.model_max_length = 512

            def __call__(self, texts, padding=True, truncation=True,
                         max_length=512, return_tensors=None):
                if isinstance(texts, str):
                    texts = [texts]
                encodings = [self._tok.encode(text) for text in texts]
                max_len = min(max(len(enc.ids) for enc in encodings), max_length)
                input_ids = []
                attention_mask = []
                for enc in encodings:
                    ids = enc.ids[:max_len]
                    ids = ids + [self.pad_token_id] * (max_len - len(ids))
                    mask = [1] * min(len(enc.ids), max_len)
                    mask = mask + [0] * (max_len - len(mask))
                    input_ids.append(ids)
                    attention_mask.append(mask)
                return {
                    "input_ids": np.asarray(input_ids, dtype=np.int64),
                    "attention_mask": np.asarray(attention_mask, dtype=np.int64),
                }

        return SimpleTokenizer(raw), "tokenizers"


def mean_pool(last_hidden_state: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = attention_mask[..., None].astype(np.float32)
    summed = (last_hidden_state * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), 1e-9, None)
    return summed / counts


def build_session(provider_name: str) -> tuple[Any, str]:
    import onnxruntime as ort

    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_options.intra_op_num_threads = 0
    sess_options.inter_op_num_threads = 0

    providers: list[str]
    lowered = provider_name.lower()
    if lowered in {"directml", "dml", "dmlexecutionprovider"}:
        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
    elif lowered in {"cpu", "cpuexecutionprovider"}:
        providers = ["CPUExecutionProvider"]
    else:
        providers = [provider_name, "CPUExecutionProvider"]

    session = ort.InferenceSession(
        str(MODEL_PATH),
        sess_options=sess_options,
        providers=providers,
    )
    active_provider = session.get_providers()[0]
    return session, active_provider


def run_embedding_case(provider_name: str, texts: list[str], batch_size: int) -> dict[str, Any]:
    tokenizer, tokenizer_backend = load_tokenizer(MODEL_DIR)
    session, active_provider = build_session(provider_name)

    warmup = texts[: min(4, len(texts))]
    inputs = tokenizer(warmup, padding=True, truncation=True, max_length=512, return_tensors="np")
    session.run(None, {
        "input_ids": np.asarray(inputs["input_ids"], dtype=np.int64),
        "attention_mask": np.asarray(inputs["attention_mask"], dtype=np.int64),
    })

    single_timings: list[float] = []
    batch_timings: list[float] = []
    vector_dim = 0

    for text in texts:
        started = time.perf_counter()
        single_inputs = tokenizer(text, padding="max_length", truncation=True,
                                  max_length=512, return_tensors="np")
        outputs = session.run(None, {
            "input_ids": np.asarray(single_inputs["input_ids"], dtype=np.int64),
            "attention_mask": np.asarray(single_inputs["attention_mask"], dtype=np.int64),
        })
        pooled = mean_pool(np.asarray(outputs[0]), np.asarray(single_inputs["attention_mask"]))
        pooled = pooled / (np.linalg.norm(pooled, axis=1, keepdims=True) + 1e-9)
        vector_dim = int(pooled.shape[-1])
        elapsed = (time.perf_counter() - started) * 1000.0
        single_timings.append(elapsed)

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        started = time.perf_counter()
        batch_inputs = tokenizer(batch, padding=True, truncation=True,
                                 max_length=512, return_tensors="np")
        outputs = session.run(None, {
            "input_ids": np.asarray(batch_inputs["input_ids"], dtype=np.int64),
            "attention_mask": np.asarray(batch_inputs["attention_mask"], dtype=np.int64),
        })
        pooled = mean_pool(np.asarray(outputs[0]), np.asarray(batch_inputs["attention_mask"]))
        pooled = pooled / (np.linalg.norm(pooled, axis=1, keepdims=True) + 1e-9)
        vector_dim = int(pooled.shape[-1])
        elapsed = (time.perf_counter() - started) * 1000.0
        batch_timings.append(elapsed)

    total_vectors = len(texts)
    total_batch_ms = sum(batch_timings) or 1.0
    throughput = round(total_vectors / (total_batch_ms / 1000.0), 3)

    return {
        "requested_provider": provider_name,
        "active_provider": active_provider,
        "tokenizer_backend": tokenizer_backend,
        "vector_dim": vector_dim,
        "single": asdict(compute_timing_stats(single_timings)),
        "batch": asdict(compute_timing_stats(batch_timings)),
        "throughput_vectors_per_sec": throughput,
    }


def build_synthetic_dataset(size: int, dim: int, seed: int = 42) -> tuple[np.ndarray, list[dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    vectors = rng.normal(size=(size, dim)).astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.clip(norms, 1e-9, None)

    records: list[dict[str, Any]] = []
    for idx in range(size):
        records.append({
            "id": f"doc-{idx}",
            "source_id": "benchmark",
            "path": f"/benchmark/doc-{idx}.md",
            "rel_path": f"doc-{idx}.md",
            "name": f"doc-{idx}.md",
            "ext": ".md",
            "type": "text",
            "size_bytes": 1024,
            "mtime": float(idx),
            "vector": vectors[idx].tolist(),
            "indexed_at": float(idx),
            "text_snippet": f"synthetic benchmark record {idx}",
            "orig_file": "",
            "status": "indexed",
        })
    return vectors, records


def benchmark_lancedb(dim: int = 768, dataset_sizes: list[int] | None = None) -> dict[str, Any]:
    import lancedb
    import pyarrow as pa

    if dataset_sizes is None:
        dataset_sizes = [1_000, 10_000, 50_000]

    if LANCEDB_DIR.exists():
        shutil.rmtree(LANCEDB_DIR)
    LANCEDB_DIR.mkdir(parents=True, exist_ok=True)

    db = lancedb.connect(str(LANCEDB_DIR))
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("source_id", pa.string()),
        pa.field("path", pa.string()),
        pa.field("rel_path", pa.string()),
        pa.field("name", pa.string()),
        pa.field("ext", pa.string()),
        pa.field("type", pa.string()),
        pa.field("size_bytes", pa.int64()),
        pa.field("mtime", pa.float64()),
        pa.field("vector", pa.list_(pa.float32(), dim)),
        pa.field("indexed_at", pa.float64()),
        pa.field("text_snippet", pa.string()),
        pa.field("orig_file", pa.string()),
        pa.field("status", pa.string()),
    ])

    results: list[dict[str, Any]] = []

    for size in dataset_sizes:
        vectors, records = build_synthetic_dataset(size, dim, seed=size)
        table_name = f"files_{size}"
        try:
            db.drop_table(table_name)
        except Exception:
            pass

        started = time.perf_counter()
        table = db.create_table(table_name, data=records, schema=schema, mode="overwrite")
        insert_ms = (time.perf_counter() - started) * 1000.0

        query_indices = random.sample(range(size), min(30, size))
        brute_force_timings: list[float] = []
        for idx in query_indices:
            query = vectors[idx].tolist()
            started = time.perf_counter()
            _ = (
                table.search(query, vector_column_name="vector")
                .metric("cosine")
                .limit(10)
                .to_list()
            )
            brute_force_timings.append((time.perf_counter() - started) * 1000.0)

        index_build_ms = None
        indexed_search_timings: list[float] = []
        if size >= 10_000:
            started = time.perf_counter()
            table.create_index(
                vector_column_name="vector",
                index_type="IVF_PQ",
                num_partitions=max(64, int(size ** 0.5)),
                metric="cosine",
            )
            index_build_ms = (time.perf_counter() - started) * 1000.0

            for idx in query_indices:
                query = vectors[idx].tolist()
                started = time.perf_counter()
                _ = (
                    table.search(query, vector_column_name="vector")
                    .metric("cosine")
                    .limit(10)
                    .to_list()
                )
                indexed_search_timings.append((time.perf_counter() - started) * 1000.0)

        results.append({
            "dataset_size": size,
            "insert_ms": round(insert_ms, 3),
            "bruteforce_search": asdict(compute_timing_stats(brute_force_timings)),
            "index_build_ms": round(index_build_ms, 3) if index_build_ms is not None else None,
            "indexed_search": asdict(compute_timing_stats(indexed_search_timings)) if indexed_search_timings else None,
        })

    return {
        "backend": "lancedb",
        "dim": dim,
        "datasets": results,
    }


def probe_alternative_backends() -> dict[str, Any]:
    import importlib.util as util

    return {
        "faiss": {"available": bool(util.find_spec("faiss"))},
        "hnswlib": {"available": bool(util.find_spec("hnswlib"))},
        "qdrant_client": {"available": bool(util.find_spec("qdrant_client"))},
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "environment": probe_environment(),
        "model": {
            "model_dir": str(MODEL_DIR),
            "model_exists": MODEL_PATH.exists(),
        },
        "embedding": {},
        "vector_search": {},
        "alternatives": probe_alternative_backends(),
    }

    if not MODEL_PATH.exists():
        report["embedding"] = {"error": f"Missing model: {MODEL_PATH}"}
    else:
        texts = SAMPLE_TEXTS * 8
        embedding_results: dict[str, Any] = {}
        for provider_name in ["CPUExecutionProvider", "DmlExecutionProvider"]:
            try:
                embedding_results[provider_name] = run_embedding_case(provider_name, texts, batch_size=8)
            except Exception as exc:
                embedding_results[provider_name] = {"error": repr(exc)}
        report["embedding"] = embedding_results

    try:
        report["vector_search"] = benchmark_lancedb(dim=768)
    except Exception as exc:
        report["vector_search"] = {"error": repr(exc)}

    report_path = OUTPUT_DIR / "benchmark-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== Benchmark Summary ===")
    print(f"Report: {report_path}")
    onnx_info = report["environment"].get("onnxruntime", {})
    print(f"Providers: {onnx_info.get('available_providers')}")

    for provider_name, result in report.get("embedding", {}).items():
        if "error" in result:
            print(f"Embedding {provider_name}: ERROR {result['error']}")
            continue
        print(
            f"Embedding {provider_name}: active={result['active_provider']}, "
            f"single_mean={result['single']['mean_ms']} ms, "
            f"batch_mean={result['batch']['mean_ms']} ms, "
            f"throughput={result['throughput_vectors_per_sec']} vec/s"
        )

    if "datasets" in report.get("vector_search", {}):
        for dataset in report["vector_search"]["datasets"]:
            print(
                f"LanceDB n={dataset['dataset_size']}: "
                f"insert={dataset['insert_ms']} ms, "
                f"search_mean={dataset['bruteforce_search']['mean_ms']} ms, "
                f"indexed_mean={dataset['indexed_search']['mean_ms'] if dataset['indexed_search'] else 'n/a'} ms"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())