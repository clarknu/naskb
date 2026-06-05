"""Standalone benchmark suite for NASKB local acceleration choices.

This script intentionally does not import or modify NASKB runtime modules. It
probes the local environment, benchmarks ONNX embedding providers, and compares
available vector-search paths with synthetic normalized vectors.
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = ROOT / "NASKB_data" / "models" / "bge-base-zh-v1.5"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


SAMPLE_TEXTS = [
    "NASKB 是一个本地向量知识库系统, 支持中文语义检索和增量索引。",
    "ONNX Runtime 可以通过不同 Execution Provider 在 CPU 或 GPU 上运行模型。",
    "LanceDB 使用嵌入式列存格式保存向量, 适合本地知识库。",
    "MCP 服务需要长期运行, 因此批量嵌入吞吐和查询延迟都很重要。",
    "这个评测关注实际可用性, 包括 provider 可见性、端到端延迟和索引性能。",
    "AMD GPU 在 Windows 上通常优先尝试 DirectML 后端, NPU 需要单独验证。",
    "语义搜索通常先把查询编码成向量, 再在向量库中查找相似内容。",
    "批量大小、最大序列长度和模型精度都会影响本地推理效率。",
]


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return math.nan
    data = sorted(values)
    index = (len(data) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return data[lower]
    return data[lower] + (data[upper] - data[lower]) * (index - lower)


def timed(fn, repeats: int) -> tuple[list[float], Any]:
    durations: list[float] = []
    last: Any = None
    for _ in range(repeats):
        start = now_ms()
        last = fn()
        durations.append(now_ms() - start)
    return durations, last


def summarize(durations_ms: list[float], items_per_call: int = 1) -> dict[str, float]:
    avg = float(np.mean(durations_ms)) if durations_ms else math.nan
    p50 = percentile(durations_ms, 0.50)
    p95 = percentile(durations_ms, 0.95)
    throughput = (items_per_call * 1000.0 / avg) if avg and not math.isnan(avg) else math.nan
    return {
        "avg_ms": round(avg, 3),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "items_per_sec": round(throughput, 3),
    }


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def run_command(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
        return completed.stdout.strip()
    except Exception as exc:
        return f"ERROR: {exc}"


def probe_gpu_windows() -> list[dict[str, str]]:
    if platform.system().lower() != "windows":
        return []
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress",
    ]
    raw = run_command(command)
    if not raw or raw.startswith("ERROR"):
        return [{"error": raw}]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]
        return parsed
    except json.JSONDecodeError:
        return [{"raw": raw}]


def probe_environment() -> dict[str, Any]:
    packages = [
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
    result: dict[str, Any] = {
        "python": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "gpus": probe_gpu_windows(),
        "packages": {pkg: package_version(pkg) for pkg in packages},
    }
    if has_module("onnxruntime"):
        import onnxruntime as ort

        result["onnxruntime_module"] = str(Path(ort.__file__).resolve())
        result["onnxruntime_available_providers"] = ort.get_available_providers()
    if has_module("torch"):
        import torch

        result["torch"] = {
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
            "mps_available": bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()),
        }
    return result


def load_tokenizer(model_dir: Path):
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
    pad_id = tokenizer.token_to_id("[PAD]") or 0
    return tokenizer, pad_id


def encode_inputs(tokenizer, pad_id: int, texts: list[str], max_length: int) -> dict[str, np.ndarray]:
    encodings = [tokenizer.encode(text) for text in texts]
    input_ids: list[list[int]] = []
    attention_mask: list[list[int]] = []
    for encoding in encodings:
        ids = encoding.ids[:max_length]
        mask = [1] * len(ids)
        ids = ids + [pad_id] * (max_length - len(ids))
        mask = mask + [0] * (max_length - len(mask))
        input_ids.append(ids)
        attention_mask.append(mask)
    return {
        "input_ids": np.asarray(input_ids, dtype=np.int64),
        "attention_mask": np.asarray(attention_mask, dtype=np.int64),
        "token_type_ids": np.zeros((len(texts), max_length), dtype=np.int64),
    }


def mean_pool(outputs: list[np.ndarray], attention_mask: np.ndarray) -> np.ndarray:
    tokens = np.asarray(outputs[0])
    mask = attention_mask.astype(np.float32)[..., None]
    pooled = (tokens * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return (pooled / np.clip(norms, 1e-9, None)).astype(np.float32)


def create_ort_session(model_path: Path, provider: str, threads: int) -> tuple[Any, str]:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    requested = [provider, "CPUExecutionProvider"] if provider != "CPUExecutionProvider" else [provider]
    session = ort.InferenceSession(str(model_path), sess_options=options, providers=requested)
    return session, session.get_providers()[0]


def benchmark_embedding(args: argparse.Namespace) -> dict[str, Any]:
    if not has_module("onnxruntime"):
        return {"available": False, "reason": "onnxruntime missing"}
    model_dir = Path(args.model_dir).resolve()
    model_path = model_dir / "model.onnx"
    if not model_path.exists():
        return {"available": False, "reason": f"model not found: {model_path}"}

    import onnxruntime as ort

    tokenizer, pad_id = load_tokenizer(model_dir)
    available = ort.get_available_providers()
    providers = ["CPUExecutionProvider"]
    if "DmlExecutionProvider" in available:
        providers.insert(0, "DmlExecutionProvider")

    texts = (SAMPLE_TEXTS * ((max(args.batch_sizes) // len(SAMPLE_TEXTS)) + 1))[: max(args.batch_sizes)]
    results: list[dict[str, Any]] = []

    for provider in providers:
        try:
            session, active_provider = create_ort_session(model_path, provider, args.threads)
            input_names = {item.name for item in session.get_inputs()}
            output_shape = session.get_outputs()[0].shape
        except Exception as exc:
            results.append({"provider": provider, "available": False, "error": repr(exc)})
            continue

        for batch_size in args.batch_sizes:
            batch_texts = texts[:batch_size]
            inputs = encode_inputs(tokenizer, pad_id, batch_texts, args.max_length)
            feed = {name: value for name, value in inputs.items() if name in input_names}

            for _ in range(args.warmup):
                mean_pool(session.run(None, feed), feed["attention_mask"])

            run_durations, vectors = timed(
                lambda: mean_pool(session.run(None, feed), feed["attention_mask"]),
                args.repeats,
            )

            def end_to_end() -> np.ndarray:
                prepared = encode_inputs(tokenizer, pad_id, batch_texts, args.max_length)
                prepared_feed = {name: value for name, value in prepared.items() if name in input_names}
                return mean_pool(session.run(None, prepared_feed), prepared_feed["attention_mask"])

            e2e_durations, _ = timed(end_to_end, args.repeats)
            results.append({
                "provider_requested": provider,
                "provider_active": active_provider,
                "batch_size": batch_size,
                "max_length": args.max_length,
                "output_shape": output_shape,
                "vector_shape": list(vectors.shape),
                "run_only": summarize(run_durations, batch_size),
                "end_to_end": summarize(e2e_durations, batch_size),
            })

    return {
        "available": True,
        "model_dir": str(model_dir),
        "available_providers": available,
        "results": results,
    }


def normalized_random(count: int, dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vectors = rng.standard_normal((count, dim), dtype=np.float32)
    vectors /= np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9, None)
    return vectors.astype(np.float32)


def benchmark_numpy_vectors(vectors: np.ndarray, queries: np.ndarray, top_k: int, repeats: int) -> dict[str, Any]:
    def search_all() -> list[np.ndarray]:
        output = []
        for query in queries:
            scores = vectors @ query
            ids = np.argpartition(scores, -top_k)[-top_k:]
            output.append(ids[np.argsort(scores[ids])[::-1]])
        return output

    durations, _ = timed(search_all, repeats)
    return summarize(durations, len(queries))


def benchmark_lancedb_vectors(vectors: np.ndarray, queries: np.ndarray, top_k: int, work_dir: Path) -> dict[str, Any]:
    if not has_module("lancedb") or not has_module("pyarrow"):
        return {"available": False, "reason": "lancedb or pyarrow missing"}
    import lancedb
    import pyarrow as pa

    db_dir = work_dir / "lancedb"
    if db_dir.exists():
        shutil.rmtree(db_dir)
    db = lancedb.connect(str(db_dir))
    dim = vectors.shape[1]
    schema = pa.schema([
        pa.field("id", pa.int64()),
        pa.field("source_id", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), dim)),
        pa.field("text", pa.string()),
    ])

    rows = [
        {
            "id": int(index),
            "source_id": "a" if index % 2 == 0 else "b",
            "vector": vectors[index].tolist(),
            "text": f"synthetic-{index}",
        }
        for index in range(len(vectors))
    ]
    start = now_ms()
    table = db.create_table("vectors", data=pa.Table.from_pylist(rows, schema=schema), mode="overwrite")
    ingest_ms = now_ms() - start

    search_durations: list[float] = []
    for query in queries:
        start = now_ms()
        table.search(query.tolist(), vector_column_name="vector").metric("cosine").limit(top_k).to_list()
        search_durations.append(now_ms() - start)

    index_result: dict[str, Any] = {"created": False}
    try:
        start = now_ms()
        table.create_index(
            vector_column_name="vector",
            index_type="IVF_PQ",
            num_partitions=max(8, min(256, int(len(vectors) ** 0.5))),
            metric="cosine",
        )
        index_result = {"created": True, "build_ms": round(now_ms() - start, 3)}
        indexed_durations: list[float] = []
        for query in queries:
            start = now_ms()
            table.search(query.tolist(), vector_column_name="vector").metric("cosine").limit(top_k).to_list()
            indexed_durations.append(now_ms() - start)
        index_result["search"] = summarize(indexed_durations, 1)
    except Exception as exc:
        index_result = {"created": False, "error": repr(exc)}

    return {
        "available": True,
        "ingest_ms": round(ingest_ms, 3),
        "search": summarize(search_durations, 1),
        "index": index_result,
    }


def benchmark_optional_vectors() -> dict[str, Any]:
    return {
        "faiss": {"available": has_module("faiss"), "package": package_version("faiss-cpu")},
        "hnswlib": {"available": has_module("hnswlib"), "package": package_version("hnswlib")},
        "qdrant_client": {"available": has_module("qdrant_client"), "package": package_version("qdrant-client")},
    }


def benchmark_vectors(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    sizes: list[int] = args.vector_counts
    results: list[dict[str, Any]] = []
    for count in sizes:
        vectors = normalized_random(count, args.dim, args.seed)
        queries = normalized_random(args.query_count, args.dim, args.seed + count)
        case_dir = output_dir / f"vectors_{count}"
        case_dir.mkdir(parents=True, exist_ok=True)
        results.append({
            "count": count,
            "dim": args.dim,
            "query_count": args.query_count,
            "top_k": args.top_k,
            "numpy_exact": benchmark_numpy_vectors(vectors, queries, args.top_k, args.vector_repeats),
            "lancedb": benchmark_lancedb_vectors(vectors, queries, args.top_k, case_dir),
        })
    return {"optional_backends": benchmark_optional_vectors(), "results": results}


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    lines.append("# NASKB Benchmark Report")
    lines.append("")
    env = report["environment"]
    lines.append("## Environment")
    lines.append(f"- Python: `{env['python']}`")
    lines.append(f"- Platform: {env['platform']}")
    lines.append(f"- CPU count: {env['cpu_count']}")
    lines.append(f"- ONNX providers: {env.get('onnxruntime_available_providers', [])}")
    if env.get("gpus"):
        lines.append(f"- GPUs: `{json.dumps(env['gpus'], ensure_ascii=False)}`")
    lines.append("")

    lines.append("## Embedding")
    emb = report["embedding"]
    if not emb.get("available"):
        lines.append(f"- Unavailable: {emb.get('reason')}")
    else:
        lines.append("| Provider requested | Provider active | Batch | Run-only avg ms | Run-only items/s | E2E avg ms | E2E items/s |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in emb["results"]:
            if not row.get("run_only"):
                lines.append(f"| {row.get('provider')} | error | - | - | - | - | - |")
                continue
            lines.append(
                f"| {row['provider_requested']} | {row['provider_active']} | {row['batch_size']} | "
                f"{row['run_only']['avg_ms']} | {row['run_only']['items_per_sec']} | "
                f"{row['end_to_end']['avg_ms']} | {row['end_to_end']['items_per_sec']} |"
            )
    lines.append("")

    lines.append("## Vector Search")
    vector = report["vectors"]
    lines.append(f"- Optional backends: `{json.dumps(vector['optional_backends'], ensure_ascii=False)}`")
    lines.append("| Backend | Count | Dim | Ingest ms | Search avg ms/query | P95 ms/query | Notes |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for case in vector["results"]:
        np_row = case["numpy_exact"]
        lines.append(f"| numpy exact | {case['count']} | {case['dim']} | - | {np_row['avg_ms']} | {np_row['p95_ms']} | batch contains {case['query_count']} queries |")
        lance = case["lancedb"]
        if lance.get("available"):
            s = lance["search"]
            note = ""
            if lance.get("index", {}).get("created"):
                note = f"IVF_PQ build {lance['index']['build_ms']} ms"
            else:
                note = f"index skipped: {lance.get('index', {}).get('error', '')[:80]}"
            lines.append(f"| LanceDB | {case['count']} | {case['dim']} | {lance['ingest_ms']} | {s['avg_ms']} | {s['p95_ms']} | {note} |")
            indexed = lance.get("index", {}).get("search")
            if indexed:
                lines.append(f"| LanceDB IVF_PQ | {case['count']} | {case['dim']} | - | {indexed['avg_ms']} | {indexed['p95_ms']} | after index |")
        else:
            lines.append(f"| LanceDB | {case['count']} | {case['dim']} | - | - | - | {lance.get('reason')} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone NASKB benchmark suite")
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--quick", action="store_true", help="Use smaller vector sizes and fewer repeats")
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--threads", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--dim", type=int, default=768)
    args = parser.parse_args()
    if args.quick:
        args.batch_sizes = [1, 8, 32]
        args.warmup = 1
        args.repeats = 3
        args.vector_counts = [1000, 10000]
        args.query_count = 10
        args.vector_repeats = 2
    else:
        args.batch_sizes = [1, 8, 32, 64]
        args.warmup = 2
        args.repeats = 8
        args.vector_counts = [1000, 10000, 50000]
        args.query_count = 20
        args.vector_repeats = 3
    return args


def main() -> int:
    args = parse_args()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir).resolve() / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "created_at": timestamp,
        "root": str(ROOT),
        "environment": probe_environment(),
        "embedding": benchmark_embedding(args),
        "vectors": benchmark_vectors(args, output_dir),
    }
    json_path = output_dir / "report.json"
    md_path = output_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, md_path)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())