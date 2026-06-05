"""NASKB — NAS Knowledge Base.

共享抽象层和基础实现，供 Skill (CLI) 和 MCP (Service) 两种形态共同使用。
"""
__version__ = "0.3.0"

from .common.config import Config
from .common.embedder import Embedder
from .common.vector_store import VectorStore, SearchResult
from .common.state import StateManager
from .common.scanner import Scanner, ScannedFile
from .common.sources import KnowledgeSource, SourceManager
from .common.model_manager import ModelManager
