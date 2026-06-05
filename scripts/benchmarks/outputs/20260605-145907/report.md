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
| CPUExecutionProvider | CPUExecutionProvider | 1 | 92.381 | 10.825 | 113.885 | 8.781 |
| CPUExecutionProvider | CPUExecutionProvider | 8 | 595.17 | 13.442 | 464.955 | 17.206 |
| CPUExecutionProvider | CPUExecutionProvider | 32 | 1943.367 | 16.466 | 1932.079 | 16.562 |

## Vector Search
- Optional backends: `{"faiss": {"available": false, "package": null}, "hnswlib": {"available": false, "package": null}, "qdrant_client": {"available": false, "package": null}}`
| Backend | Count | Dim | Ingest ms | Search avg ms/query | P95 ms/query | Notes |
|---|---:|---:|---:|---:|---:|---|
| numpy exact | 1000 | 768 | - | 1.898 | 1.928 | batch contains 10 queries |
| LanceDB | 1000 | 768 | 56.739 | 9.79 | 11.818 | IVF_PQ build 262.942 ms |
| LanceDB IVF_PQ | 1000 | 768 | - | 10.251 | 10.824 | after index |
| numpy exact | 10000 | 768 | - | 12.998 | 13.418 | batch contains 10 queries |
| LanceDB | 10000 | 768 | 275.602 | 25.976 | 27.725 | IVF_PQ build 3921.781 ms |
| LanceDB IVF_PQ | 10000 | 768 | - | 26.802 | 27.886 | after index |
