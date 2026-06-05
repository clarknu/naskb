"""NASKB Common — 共享模块。

包含跨 Skill/MCP 形态复用的所有核心实现：
- Config: 配置管理
- Embedder: ONNX Runtime 嵌入模型
- VectorStore: LanceDB 向量数据库
- StateManager: SQLite 索引进度跟踪
- Scanner: 文件扫描与排除规则
- SourceManager: 多知识来源管理
- ModelManager: ONNX 模型下载与缓存
- FileSystemAdapter: 文件系统抽象层
"""
