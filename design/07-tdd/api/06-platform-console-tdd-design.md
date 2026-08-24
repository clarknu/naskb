# TDD 设计（API）：平台服务

> 基于 API 设计 v1 | 工作流 v1 | 后端架构 v1（L3）
> 日期：2026-08-24 | Stage: API TDD
> 反向记录说明（DD-004）：既有套件映射 + 追溯链补齐。

## 测试范围

| API 端点 | 方法 | 涉及工作流 | 涉及实体 | 既有测试 |
|----------|------|-----------|---------|---------|
| /api/tree、/api/files/{rid}、/download、/preview、/parsed、/thumbnail | GET | section: download-flow / preview-flow | Resource/FolderEntry | api/test_content_access.py |
| /api/jobs、/api/jobs/{job_id} | GET | section: job-flow | Job（VO） | api/test_server_api.py |
| /api/config/public | GET | section: rules | — | api/test_server_api.py（auth 用例） |
| 认证（Bearer/匿名） | — | section: rules（R001） | — | api/test_server_api.py（TestClient open_client/locked_client） |
| Range/ETag | — | section: download-flow | RangeRequest | unit/test_ranges.py、api/test_content_access.py |

## 追溯矩阵

| 测试用例 | 正向链 | 反向链 | 用户旅程 |
|---------|--------|--------|---------|
| TC-P02 | workflow:resolve.outputs.fs/path → GET /api/files/{rid} → ER:Resource | ER:Resource ← files/{rid} ← workflow:resolve | 浏览→元数据→预览→下载 |
| TC-P08 | workflow:submit.outputs.job_id → GET /api/jobs/{id} → ER:Job | ER:Job ← jobs/{id} ← workflow:submit | 任务观察 |

## 用户旅程覆盖矩阵

| 旅程 | 涉及 API | 覆盖测试用例 | 状态 |
|------|---------|-------------|------|
| 浏览→预览（全矩阵）→下载（断点续传） | /api/tree、files/{rid}(/preview|/parsed|/thumbnail|/download) | TC-P01~TC-P09 | ✅ |
| 任务生命周期 | /api/jobs、/api/jobs/{id} | TC-P08~TC-P09 | ✅ |

## 测试用例

### TC-P01: 目录树
- **类型**: 正常流程 ｜ **断言清单**: ✅ dirs/files 结构与字段（rel_path/name/file_count/summary；resource_id/size_bytes/summary/category/status）

### TC-P02: 文件元数据
- **类型**: 正常流程 ｜ **断言清单**: ✅ resource 字段完整（含 hash_algorithm 双形态）；✅ download_url 生成

### TC-P03: 预览矩阵（全类型）
- **类型**: 边界条件 ｜ **断言清单**: ✅ image/video/audio/pdf/text/html/office/parsed 逐类断言；✅ 不支持类型 → reason（可下载后本地打开）；✅ office 大小限制（≤30MB）

### TC-P04: 解析视图
- **类型**: 正常流程 ｜ **断言清单**: ✅ rw 源 artifact HTML 可渲染；✅ ro 源无解析产物 → 明确提示

### TC-P05: 缩略图
- **类型**: 正常流程 ｜ **断言清单**: ✅ 图片（≤12MB）/视频（第 4 秒,≤100MB）生成；✅ 缓存命中不重复生成

### TC-P06: 下载代理 Range/ETag
- **类型**: 正常流程 ｜ **断言清单**: ✅ bytes=a-b/plain/-suffix 三形态；✅ 单区间拒绝多区间；✅ 304 If-None-Match 命中；✅ 416 越界；✅ 503 stale

### TC-P07: 认证与匿名
- **类型**: 异常流程 ｜ **断言清单**: ✅ 无 token 写端点 → 401；✅ Bearer 正确 → 200；✅ anonymous_read 下公开 GET 免 token；✅ 对比 compare_digest

### TC-P08: 任务生命周期
- **类型**: 正常流程 ｜ **断言清单**: ✅ pending→running→completed（progress/result）；✅ failed 带 error；✅ 串行（max_workers=1）语义

### TC-P09: 公开配置
- **类型**: 正常流程 ｜ **断言清单**: ✅ auth_required/anonymous_read 与配置一致
