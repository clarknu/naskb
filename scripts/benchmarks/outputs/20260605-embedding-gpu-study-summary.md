# Embedding GPU Study Summary

## Source Artifacts

- Baseline batch benchmark: `scripts/benchmarks/outputs/20260605-150038/report.md`
- Probe scripts:
  - `scripts/benchmarks/embedding_parallel_probe.py`
  - `scripts/benchmarks/retrieval_compute_probe.py`

## 1. Text Embedding: CPU vs DirectML

Based on `20260605-150038/report.md`:

| Provider | Batch | Avg ms | Items/s |
|---|---:|---:|---:|
| DirectML | 1 | 28.788 | 34.736 |
| DirectML | 8 | 390.870 | 20.467 |
| DirectML | 32 | 1336.907 | 23.936 |
| DirectML | 64 | 3882.539 | 16.484 |
| CPU | 1 | 133.608 | 7.485 |
| CPU | 8 | 1193.245 | 6.704 |
| CPU | 32 | 2617.810 | 12.224 |
| CPU | 64 | 10744.251 | 5.957 |

Observations:

- DirectML is clearly faster than CPU for embedding on this machine.
- Best observed DirectML throughput is around batch 32.
- DirectML batch 64 regresses noticeably, suggesting over-batching hurts this iGPU.

## 2. Text Embedding: Serial vs Parallel

Measured with `embedding_parallel_probe.py`, 16 single-text tasks:

### CPUExecutionProvider

| Workers | Wall ms | Throughput tasks/s | Mean latency ms | P95 latency ms |
|---|---:|---:|---:|---:|
| 1 | 1475.792 | 10.842 | 59.941 | 65.522 |
| 2 | 1854.834 | 8.626 | 104.754 | 178.434 |
| 4 | 3335.026 | 4.798 | 384.527 | 580.667 |

### DmlExecutionProvider

| Workers | Result |
|---|---|
| 1 | wall 1335.844 ms, throughput 11.977 tasks/s, mean latency 35.268 ms, p95 60.732 ms |
| 2 | process exited with code 1 and no Python traceback |
| 4 | process exited with code 1 and no Python traceback |

Observations:

- CPU parallelism is counterproductive for this embedding workload.
- DirectML single-worker serial mode is the best stable mode observed.
- Multi-session DirectML concurrency appears unstable in the current environment.

## 3. Alternative GPU Routes

### DirectML FP16 model

Attempted by converting the ONNX model with `onnxconverter-common`.

Result:

- FP16 conversion succeeded as a file.
- DirectML session creation failed for the converted model with ONNX type mismatch.

Error excerpt:

`Type Error: Type (tensor(float16)) ... does not match expected type (tensor(float))`

Conclusion:

- Current exported BGE ONNX model is not directly usable with this naive FP16 conversion path.

### torch-directml

Attempted via `pip index versions torch-directml`.

Result:

- No matching distribution found for the current environment.

Conclusion:

- `torch-directml` is not a viable benchmark path in the current Python environment.

## 4. Retrieval Compute: CPU vs DirectML

Measured with warmed-up `retrieval_compute_probe.py` on brute-force score computation only:

| Provider | Vector count | Query count | Mean ms | P95 ms |
|---|---:|---:|---:|---:|
| DirectML | 10000 | 8 | 6.986 | 7.223 |
| CPU | 10000 | 8 | 1.414 | 1.524 |
| DirectML | 50000 | 8 | 36.707 | 46.344 |
| CPU | 50000 | 8 | 6.922 | 7.232 |

Observations:

- Even for pure dense similarity score computation, CPU is faster than DirectML here.
- This supports keeping retrieval on CPU while letting GPU focus on embedding.

## 5. Practical Decision

Recommended current strategy:

1. Use DirectML for text embedding.
2. Keep embedding execution serial or at most extremely conservative; do not enable multi-session DML concurrency.
3. Keep vector retrieval on CPU.
4. Do not prioritize FP16 DirectML or torch-directml in the current environment until the model/export/runtime compatibility problem is solved.