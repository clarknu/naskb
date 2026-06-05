# NASKB Benchmark Suite

This directory contains standalone benchmarking tools for evaluating local
hardware acceleration and vector retrieval options without modifying the main
application code.

Current coverage:

- Environment probe: Python, packages, ONNX Runtime providers
- Embedding benchmark: ONNX Runtime CPU vs DirectML (when available)
- Vector search benchmark: LanceDB add/search/index timings
- Optional backend probe: FAISS, hnswlib, qdrant-client availability only

Primary entry point:

- `run_benchmarks.py`

Example:

```powershell
& .\.venv\Scripts\python.exe .\scripts\benchmarks\run_benchmarks.py
```

Outputs:

- Console summary
- JSON report written to `scripts/benchmarks/output/benchmark-report.json`