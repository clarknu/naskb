# NASKB Benchmark Report

## Environment
- Python: `C:\Sync\NASKB\.venv\Scripts\python.exe`
- Platform: Windows-11-10.0.26200-SP0
- CPU count: 16
- ONNX providers: ['AzureExecutionProvider', 'CPUExecutionProvider']
- GPUs: `[{"Name": "AMD Radeon 780M Graphics", "AdapterRAM": 536870912, "DriverVersion": "32.0.23033.1002"}]`

## Embedding
| Provider requested | Provider active | Batch | Run-only avg ms | Run-only items/s | E2E avg ms | E2E items/s |
|---|---:|---:|---:|---:|---:|---:|
| CPUExecutionProvider | CPUExecutionProvider | 1 | 61.989 | 16.132 | 62.804 | 15.923 |
| CPUExecutionProvider | CPUExecutionProvider | 8 | 445.909 | 17.941 | 452.785 | 17.668 |
| CPUExecutionProvider | CPUExecutionProvider | 32 | 1886.147 | 16.966 | 2004.991 | 15.96 |

## Vector Search
- Optional backends: `{"faiss": {"available": false, "package": null}, "hnswlib": {"available": false, "package": null}, "qdrant_client": {"available": false, "package": null}}`
| Backend | Count | Dim | Ingest ms | Search avg ms/query | P95 ms/query | Notes |
|---|---:|---:|---:|---:|---:|---|
| numpy exact | 1000 | 768 | - | 2.317 | 2.357 | batch contains 10 queries |
| LanceDB | 1000 | 768 | 52.696 | 12.311 | 14.786 | IVF_PQ build 289.812 ms |
| LanceDB IVF_PQ | 1000 | 768 | - | 8.665 | 11.555 | after index |
| numpy exact | 10000 | 768 | - | 15.487 | 16.184 | batch contains 10 queries |
| LanceDB | 10000 | 768 | 284.314 | 26.57 | 27.936 | IVF_PQ build 4415.56 ms |
| LanceDB IVF_PQ | 10000 | 768 | - | 8.723 | 10.543 | after index |
