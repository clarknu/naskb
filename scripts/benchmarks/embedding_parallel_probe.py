"""Probe serial vs parallel embedding latency on CPU and DirectML."""
from __future__ import annotations

import json
import math
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "NASKB_data" / "models" / "bge-base-zh-v1.5" / "model.onnx"
TOKENIZER_PATH = ROOT / "NASKB_data" / "models" / "bge-base-zh-v1.5" / "tokenizer.json"
THREAD_STATE = threading.local()

TEXTS = [
    "NASKB 的本地知识库场景重视中文语义检索。",
    "GPU 向量化需要同时看吞吐和单任务延迟。",
    "并发嵌入不一定更快，特别是共享 GPU 时。",
    "CPU 检索和 GPU embedding 可以形成自然分工。",
    "小 batch 往往比极大 batch 更稳定。",
    "MCP 服务更在意稳定延迟，而不只是峰值吞吐。",
    "DirectML 的收益取决于模型、batch 和显存压力。",
    "评测需要区分 provider 激活和真实性能收益。",
]


def compute_stats(values: list[float]) -> dict[str, float]:
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


def get_resources(provider: str):
    cache = getattr(THREAD_STATE, "cache", None)
    if cache is None:
        cache = {}
        THREAD_STATE.cache = cache
    if provider in cache:
        return cache[provider]

    tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
    pad_id = tokenizer.token_to_id("[PAD]") or 0

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = 0
    options.inter_op_num_threads = 1
    providers = [provider, "CPUExecutionProvider"] if provider == "DmlExecutionProvider" else ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(MODEL_PATH), sess_options=options, providers=providers)
    input_names = {item.name for item in session.get_inputs()}
    cache[provider] = (tokenizer, pad_id, session, input_names, session.get_providers()[0])
    return cache[provider]


def encode_single(provider: str, text: str, max_length: int = 128) -> tuple[float, str]:
    tokenizer, pad_id, session, input_names, active = get_resources(provider)
    enc = tokenizer.encode(text)
    ids = enc.ids[:max_length]
    ids = ids + [pad_id] * (max_length - len(ids))
    mask = [1] * min(len(enc.ids), max_length)
    mask = mask + [0] * (max_length - len(mask))
    feed = {
        "input_ids": np.asarray([ids], dtype=np.int64),
        "attention_mask": np.asarray([mask], dtype=np.int64),
    }
    filtered = {k: v for k, v in feed.items() if k in input_names}
    started = time.perf_counter()
    session.run(None, filtered)
    return (time.perf_counter() - started) * 1000.0, active


def run_mode(provider: str, workers: int, tasks: int) -> dict:
    texts = (TEXTS * ((tasks // len(TEXTS)) + 2))[:tasks]
    latencies: list[float] = []
    active_provider = None
    started = time.perf_counter()
    if workers == 1:
        for text in texts:
            latency, active_provider = encode_single(provider, text)
            latencies.append(latency)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(encode_single, provider, text) for text in texts]
            for future in as_completed(futures):
                latency, active_provider = future.result()
                latencies.append(latency)
    wall_ms = (time.perf_counter() - started) * 1000.0
    return {
        "workers": workers,
        "requested_provider": provider,
        "active_provider": active_provider,
        "wall_ms": round(wall_ms, 3),
        "throughput_tasks_per_sec": round(tasks / (wall_ms / 1000.0), 3),
        "latency": compute_stats(latencies),
    }


def main() -> int:
    providers = ["CPUExecutionProvider"]
    if "DmlExecutionProvider" in ort.get_available_providers():
        providers.insert(0, "DmlExecutionProvider")

    report = {"available_providers": ort.get_available_providers(), "results": []}
    for provider in providers:
        for workers in [1, 2, 4]:
            report["results"].append(run_mode(provider, workers, tasks=16))

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())