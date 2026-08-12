"""NASKB Common — 共享核心实现（v2）。

- Config: 配置管理（LLM/WebDAV/MinerU/analyzer）
- NaskbStore: .naskb 目录隐藏描述仓库（index.json + folder.json + artifacts）
- FileSystemAdapter: 文件系统抽象（local / webdav）
- analyzer/: 文档/图片/音频/视频/MinerU/folder/reorganizer 分析引擎
- llm: DeepSeek/MiMo 客户端
"""
