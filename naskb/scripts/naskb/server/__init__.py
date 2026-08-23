"""平台服务包（v3，REQ-R7-01）：FastAPI 常驻服务。

- app.create_app(config)：装配 REST（旧契约平移 + 新平台 API）与 Web UI 静态托管
- auth：单管理员 Bearer token（+匿名只读开关）
- scheduler：来源周期扫描调度（进程内线程，无新中间件）
"""
