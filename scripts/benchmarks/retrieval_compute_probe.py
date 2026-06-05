"""Probe CPU vs DirectML brute-force retrieval score computation."""
from __future__ import annotations

import json
import math
import statistics
import tempfile
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper


ROOT = Path(__file__).resolve().parents[2]


def stats(values: list[float]) -> dict[str, float]:
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
        "p50_ms": round(percentile(0.5), 3),
        "p95_ms": round(percentile(0.95), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def normalized_random(count: int, dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vectors = rng.standard_normal((count, dim), dtype=np.float32)
    vectors /= np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9, None)
    return vectors.astype(np.float32)


def make_model(dim: int, path: Path) -> Path:
    db_vectors = helper.make_tensor_value_info("db_vectors", TensorProto.FLOAT, [None, dim])
    queries = helper.make_tensor_value_info("queries", TensorProto.FLOAT, [None, dim])
    scores = helper.make_tensor_value_info("scores", TensorProto.FLOAT, [None, None])
    nodes = [
        helper.make_node("Transpose", ["db_vectors"], ["db_vectors_t"], perm=[1, 0]),
        helper.make_node("MatMul", ["queries", "db_vectors_t"], ["scores"]),
    ]
    graph = helper.make_graph(nodes, "retrieval_probe", [db_vectors, queries], [scores])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    onnx.save(model, str(path))
    return path


def benchmark(provider: str, model_path: Path) -> dict:
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if provider == "DmlExecutionProvider":
        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(model_path), sess_options=options, providers=providers)
    active = session.get_providers()[0]

    results = []
    for vector_count, query_count in [(10000, 8), (50000, 8)]:
        db_vectors = normalized_random(vector_count, 768, vector_count)
        queries = normalized_random(query_count, 768, vector_count + 1)
        session.run(None, {"db_vectors": db_vectors, "queries": queries})
        durations = []
        for _ in range(5):
            started = time.perf_counter()
            session.run(None, {"db_vectors": db_vectors, "queries": queries})
            durations.append((time.perf_counter() - started) * 1000.0)
        results.append({
            "vector_count": vector_count,
            "query_count": query_count,
            "stats": stats(durations),
        })

    return {"requested_provider": provider, "active_provider": active, "results": results}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="naskb-retrieval-probe-") as tmp:
        model_path = make_model(768, Path(tmp) / "retrieval.onnx")
        providers = ["CPUExecutionProvider"]
        if "DmlExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "DmlExecutionProvider")
        report = {
            "available_providers": ort.get_available_providers(),
            "results": [benchmark(provider, model_path) for provider in providers],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())