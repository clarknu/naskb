"""Focused benchmark for embedding GPU acceleration and serial/parallel tradeoffs.

This script is intentionally independent from the main NASKB runtime. It studies:

- ONNX Runtime CPU vs DirectML for embedding inference
- Optional FP16 model conversion for DirectML
- Serial vs multi-session parallel embedding performance
- CPU vs DirectML brute-force similarity computation for retrieval-style workloads
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import tempfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "NASKB_data" / "models" / "bge-base-zh-v1.5"
MODEL_PATH = MODEL_DIR / "model.onnx"
OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"
THREAD_STATE = threading.local()


SAMPLE_TEXTS = [
    "NASKB 的重点是本地知识库、中文友好以及语义检索性能。",
    "文本向量化如果走 GPU，需要确认 provider 真正激活并且吞吐提升可持续。",
    "DirectML 在 Windows 上面向广泛 GPU 兼容，但不同模型和 batch 的表现差异很大。",
    "如果并发嵌入导致单任务延迟明显升高，串行或小并发可能更适合 MCP 服务。",
    "向量检索未必需要 GPU，因为 CPU 索引可以和 GPU embedding 自然分工。",
    "批量向量化的瓶颈可能来自 tokenization、显存传输或者计算图中的某些算子。",
    "我们需要同时看吞吐量和单任务延迟，而不是只看总耗时。",
    "AMD 780M 这类 iGPU 更要避免盲目增大 batch，否则共享内存压力会很明显。",
]


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}
    ordered = sorted(values)

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

    return {
        "count": len(values),
        "mean_ms": round(statistics.mean(values), 3),
        "p50_ms": round(percentile(0.50), 3),
        "p95_ms": round(percentile(0.95), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def has_dml() -> bool:
    import onnxruntime as ort

    return "DmlExecutionProvider" in ort.get_available_providers()


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
    }


def mean_pool(outputs: list[np.ndarray], attention_mask: np.ndarray) -> np.ndarray:
    token_embeddings = np.asarray(outputs[0])
    mask = attention_mask.astype(np.float32)[..., None]
    pooled = (token_embeddings * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return (pooled / np.clip(norms, 1e-9, None)).astype(np.float32)


def create_session(model_path: Path, provider: str, intra_threads: int = 0):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = intra_threads
    options.inter_op_num_threads = 1
    if provider == "DmlExecutionProvider":
        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(model_path), sess_options=options, providers=providers)
    return session, session.get_providers()[0]


def convert_fp16_model(source: Path, output_dir: Path) -> Path:
    import onnx
    from onnxconverter_common import float16

    fp16_path = output_dir / "model.fp16.onnx"
    if fp16_path.exists():
        return fp16_path

    model = onnx.load(str(source))
    converted = float16.convert_float_to_float16(model, keep_io_types=True)
    onnx.save(converted, str(fp16_path))
    return fp16_path


def benchmark_embedding_method(
    name: str,
    model_path: Path,
    provider: str,
    tokenizer,
    pad_id: int,
    batch_sizes: list[int],
    max_length: int,
    repeats: int,
) -> dict[str, Any]:
    try:
        session, active = create_session(model_path, provider)
    except Exception as exc:
        return {"name": name, "available": False, "error": repr(exc)}

    input_names = {item.name for item in session.get_inputs()}
    text_pool = (SAMPLE_TEXTS * ((max(batch_sizes) // len(SAMPLE_TEXTS)) + 2))[: max(batch_sizes)]
    cases: list[dict[str, Any]] = []

    for batch_size in batch_sizes:
        batch_texts = text_pool[:batch_size]
        feed = encode_inputs(tokenizer, pad_id, batch_texts, max_length)
        filtered_feed = {key: value for key, value in feed.items() if key in input_names}

        warmup_runs = 2 if batch_size <= 32 else 1
        for _ in range(warmup_runs):
            mean_pool(session.run(None, filtered_feed), filtered_feed["attention_mask"])

        durations: list[float] = []
        for _ in range(repeats):
            started = time.perf_counter()
            mean_pool(session.run(None, filtered_feed), filtered_feed["attention_mask"])
            durations.append((time.perf_counter() - started) * 1000.0)

        case_stats = stats(durations)
        case_stats["items_per_sec"] = round(batch_size / (case_stats["mean_ms"] / 1000.0), 3) if case_stats["mean_ms"] else 0.0
        cases.append({"batch_size": batch_size, "stats": case_stats})

    return {
        "name": name,
        "available": True,
        "provider_requested": provider,
        "provider_active": active,
        "model_path": str(model_path),
        "cases": cases,
    }


def get_thread_resources(model_path: Path, provider: str):
    cache = getattr(THREAD_STATE, "cache", None)
    if cache is None:
        cache = {}
        THREAD_STATE.cache = cache
    key = (str(model_path), provider)
    if key not in cache:
        tokenizer, pad_id = load_tokenizer(MODEL_DIR)
        session, _ = create_session(model_path, provider)
        input_names = {item.name for item in session.get_inputs()}
        cache[key] = (tokenizer, pad_id, session, input_names)
    return cache[key]


def worker_encode(model_path: Path, provider: str, text: str, max_length: int) -> float:
    tokenizer, pad_id, session, input_names = get_thread_resources(model_path, provider)
    input_names = {item.name for item in session.get_inputs()}
    feed = encode_inputs(tokenizer, pad_id, [text], max_length)
    filtered_feed = {key: value for key, value in feed.items() if key in input_names}
    started = time.perf_counter()
    mean_pool(session.run(None, filtered_feed), filtered_feed["attention_mask"])
    return (time.perf_counter() - started) * 1000.0


def benchmark_parallelism(
    name: str,
    model_path: Path,
    provider: str,
    max_length: int,
    tasks: int,
    worker_options: list[int],
) -> dict[str, Any]:
    texts = (SAMPLE_TEXTS * ((tasks // len(SAMPLE_TEXTS)) + 2))[:tasks]
    results: list[dict[str, Any]] = []

    serial_latencies: list[float] = []
    try:
        started = time.perf_counter()
        for text in texts:
            serial_latencies.append(worker_encode(model_path, provider, text, max_length))
        total_serial_ms = (time.perf_counter() - started) * 1000.0
        results.append({
            "mode": "serial",
            "workers": 1,
            "wall_ms": round(total_serial_ms, 3),
            "throughput_tasks_per_sec": round(tasks / (total_serial_ms / 1000.0), 3),
            "latency": stats(serial_latencies),
        })
    except Exception as exc:
        results.append({
            "mode": "serial",
            "workers": 1,
            "error": repr(exc),
        })

    for workers in worker_options:
        submit_started = time.perf_counter()
        task_latencies: list[float] = []
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(worker_encode, model_path, provider, text, max_length) for text in texts]
                for future in as_completed(futures):
                    task_latencies.append(future.result())
            wall_ms = (time.perf_counter() - submit_started) * 1000.0
            results.append({
                "mode": "parallel_multi_session",
                "workers": workers,
                "wall_ms": round(wall_ms, 3),
                "throughput_tasks_per_sec": round(tasks / (wall_ms / 1000.0), 3),
                "latency": stats(task_latencies),
            })
        except Exception as exc:
            results.append({
                "mode": "parallel_multi_session",
                "workers": workers,
                "error": repr(exc),
            })

    return {"name": name, "provider": provider, "model_path": str(model_path), "runs": results}


def make_retrieval_model(dim: int, output_path: Path) -> Path:
    import onnx
    from onnx import TensorProto, helper

    if output_path.exists():
        return output_path

    db_vectors = helper.make_tensor_value_info("db_vectors", TensorProto.FLOAT, [None, dim])
    queries = helper.make_tensor_value_info("queries", TensorProto.FLOAT, [None, dim])
    transposed = helper.make_tensor_value_info("db_vectors_t", TensorProto.FLOAT, [dim, None])
    scores = helper.make_tensor_value_info("scores", TensorProto.FLOAT, [None, None])

    nodes = [
        helper.make_node("Transpose", ["db_vectors"], ["db_vectors_t"], perm=[1, 0]),
        helper.make_node("MatMul", ["queries", "db_vectors_t"], ["scores"]),
    ]
    graph = helper.make_graph(nodes, "retrieval_benchmark", [db_vectors, queries], [scores], value_info=[transposed])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    onnx.save(model, str(output_path))
    return output_path


def normalized_random(count: int, dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vectors = rng.standard_normal((count, dim), dtype=np.float32)
    vectors /= np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9, None)
    return vectors.astype(np.float32)


def benchmark_retrieval_compute(
    output_dir: Path,
    provider: str,
    dim: int,
    vector_counts: list[int],
    query_count: int,
    repeats: int,
) -> dict[str, Any]:
    retrieval_model = make_retrieval_model(dim, output_dir / f"retrieval_{dim}.onnx")
    try:
        session, active = create_session(retrieval_model, provider)
    except Exception as exc:
        return {"provider": provider, "available": False, "error": repr(exc)}

    results: list[dict[str, Any]] = []
    for count in vector_counts:
        db_vectors = normalized_random(count, dim, seed=count)
        queries = normalized_random(query_count, dim, seed=count + 1)
        durations: list[float] = []
        for _ in range(repeats):
            started = time.perf_counter()
            session.run(None, {"db_vectors": db_vectors, "queries": queries})
            durations.append((time.perf_counter() - started) * 1000.0)
        results.append({
            "vector_count": count,
            "query_count": query_count,
            "stats": stats(durations),
        })

    return {"provider": provider, "active": active, "available": True, "results": results}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    import onnxruntime as ort

    output_dir = OUTPUT_ROOT / time.strftime("%Y%m%d-%H%M%S")
    ensure_dir(output_dir)
    tokenizer, pad_id = load_tokenizer(MODEL_DIR)
    report: dict[str, Any] = {
        "created_at": output_dir.name,
        "python": os.fspath(Path(os.__file__).resolve().parent.parent),
        "available_providers": ort.get_available_providers(),
        "embedding_methods": [],
        "parallelism": [],
        "retrieval_compute": [],
        "notes": [],
    }

    fp16_path: Path | None = None
    if args.try_fp16:
        try:
            fp16_path = convert_fp16_model(MODEL_PATH, output_dir)
            report["notes"].append(f"FP16 model created: {fp16_path}")
        except Exception as exc:
            report["notes"].append(f"FP16 conversion failed: {exc!r}")

    methods = [
        ("ort_cpu_fp32", MODEL_PATH, "CPUExecutionProvider"),
    ]
    if has_dml():
        methods.append(("ort_dml_fp32", MODEL_PATH, "DmlExecutionProvider"))
        if fp16_path is not None:
            methods.append(("ort_dml_fp16", fp16_path, "DmlExecutionProvider"))

    for name, model_path, provider in methods:
        report["embedding_methods"].append(
            benchmark_embedding_method(name, model_path, provider, tokenizer, pad_id, args.batch_sizes, args.max_length, args.repeats)
        )
        report["parallelism"].append(
            benchmark_parallelism(name, model_path, provider, args.max_length, args.parallel_tasks, args.parallel_workers)
        )

    retrieval_providers = ["CPUExecutionProvider"]
    if has_dml():
        retrieval_providers.append("DmlExecutionProvider")
    for provider in retrieval_providers:
        report["retrieval_compute"].append(
            benchmark_retrieval_compute(output_dir, provider, args.dim, args.vector_counts, args.query_count, args.repeats)
        )

    json_path = output_dir / "embedding_gpu_study.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(json_path)
    return report


def print_summary(report: dict[str, Any]) -> None:
    print(f"Providers: {report['available_providers']}")
    for method in report["embedding_methods"]:
        if not method.get("available"):
            print(f"Embedding {method['name']}: ERROR {method['error']}")
            continue
        batch_1 = next((case for case in method["cases"] if case["batch_size"] == 1), None)
        batch_32 = next((case for case in method["cases"] if case["batch_size"] == 32), None)
        print(
            f"Embedding {method['name']}: active={method['provider_active']}, "
            f"b1={batch_1['stats']['mean_ms'] if batch_1 else 'n/a'} ms, "
            f"b32_items_s={batch_32['stats'].get('items_per_sec') if batch_32 else 'n/a'}"
        )
    for parallel in report["parallelism"]:
        print(f"Parallel {parallel['name']}:")
        for run in parallel["runs"]:
            if run.get("error"):
                print(f"  {run['mode']} workers={run['workers']} ERROR={run['error']}")
                continue
            print(
                f"  {run['mode']} workers={run['workers']} wall={run['wall_ms']} ms "
                f"throughput={run['throughput_tasks_per_sec']} t/s p95={run['latency']['p95_ms']} ms"
            )
    for retrieval in report["retrieval_compute"]:
        if not retrieval.get("available"):
            print(f"Retrieval {retrieval['provider']}: ERROR {retrieval['error']}")
            continue
        for case in retrieval["results"]:
            print(
                f"Retrieval {retrieval['provider']} n={case['vector_count']} q={case['query_count']} "
                f"mean={case['stats']['mean_ms']} ms p95={case['stats']['p95_ms']} ms"
            )
    print(f"Report: {report['report_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Focused GPU study for NASKB embeddings and retrieval")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--try-fp16", action="store_true")
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--dim", type=int, default=768)
    args = parser.parse_args()
    if args.quick:
        args.batch_sizes = [1, 8, 32]
        args.repeats = 3
        args.parallel_tasks = 16
        args.parallel_workers = [2, 4]
        args.vector_counts = [10000, 50000]
        args.query_count = 8
    else:
        args.batch_sizes = [1, 8, 32, 64]
        args.repeats = 6
        args.parallel_tasks = 32
        args.parallel_workers = [2, 4, 8]
        args.vector_counts = [10000, 50000]
        args.query_count = 16
    return args


def main() -> int:
    try:
        report = build_report(parse_args())
        print_summary(report)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())