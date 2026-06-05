# NASKB Benchmark Report

## Environment
- Python: `C:\Sync\NASKB\.venv\Scripts\python.exe`
- Platform: Windows-11-10.0.26200-SP0
- CPU count: 16
- ONNX providers: ['DmlExecutionProvider', 'CPUExecutionProvider']
- GPUs: `[{"Name": "AMD Radeon 780M Graphics", "AdapterRAM": 536870912, "DriverVersion": "32.0.23033.1002"}]`

## Embedding
| Provider requested | Provider active | Batch | Run-only avg ms | Run-only items/s | E2E avg ms | E2E items/s |
|---|---:|---:|---:|---:|---:|---:|
| DmlExecutionProvider | DmlExecutionProvider | 1 | 28.788 | 34.736 | 27.473 | 36.399 |
| DmlExecutionProvider | DmlExecutionProvider | 8 | 390.87 | 20.467 | 367.933 | 21.743 |
| DmlExecutionProvider | DmlExecutionProvider | 32 | 1336.907 | 23.936 | 1625.685 | 19.684 |
| DmlExecutionProvider | DmlExecutionProvider | 64 | 3882.539 | 16.484 | 5105.584 | 12.535 |
| CPUExecutionProvider | CPUExecutionProvider | 1 | 133.608 | 7.485 | 121.549 | 8.227 |
| CPUExecutionProvider | CPUExecutionProvider | 8 | 1193.245 | 6.704 | 1176.033 | 6.803 |
| CPUExecutionProvider | CPUExecutionProvider | 32 | 2617.81 | 12.224 | 2352.897 | 13.6 |
| CPUExecutionProvider | CPUExecutionProvider | 64 | 10744.251 | 5.957 | 11785.002 | 5.431 |

## Vector Search
- Optional backends: `{"faiss": {"available": false, "package": null}, "hnswlib": {"available": false, "package": null}, "qdrant_client": {"available": false, "package": null}}`
| Backend | Count | Dim | Ingest ms | Search avg ms/query | P95 ms/query | Notes |
|---|---:|---:|---:|---:|---:|---|
| numpy exact | 1000 | 768 | - | 17.349 | 18.347 | batch contains 20 queries |
| LanceDB | 1000 | 768 | 124.121 | 26.389 | 36.846 | IVF_PQ build 543.184 ms |
| LanceDB IVF_PQ | 1000 | 768 | - | 23.403 | 29.636 | after index |
| numpy exact | 10000 | 768 | - | 86.755 | 92.176 | batch contains 20 queries |
| LanceDB | 10000 | 768 | 508.835 | 83.324 | 137.172 | IVF_PQ build 6897.498 ms |
| LanceDB IVF_PQ | 10000 | 768 | - | 18.624 | 32.161 | after index |
| numpy exact | 50000 | 768 | - | 303.3 | 390.021 | batch contains 20 queries |
| LanceDB | 50000 | 768 | 2674.524 | 420.598 | 557.828 | IVF_PQ build 37605.947 ms |
| LanceDB IVF_PQ | 50000 | 768 | - | 16.624 | 20.103 | after index |
