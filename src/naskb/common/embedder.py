"""Text embedding using ONNX Runtime.

Supports DirectML (Windows GPU via DX12) and CPU fallback.
Provides BaseEmbedder abstract interface for future backend extensibility.
"""
from __future__ import annotations

import numpy as np
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Union


class BaseEmbedder(ABC):
    """文本嵌入抽象接口。

    允许 Skill 和 MCP 形态使用不同的嵌入后端：
    - ONNXEmbedder: 本地 ONNX Runtime (DirectML/CPU)
    - RemoteEmbedder: 远程嵌入服务 (未来扩展)
    """

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度 (768 或 1024)."""
        ...

    @abstractmethod
    def encode(self, text: str) -> np.ndarray:
        """编码单条文本为向量 (dim,)."""
        ...

    @abstractmethod
    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """批量编码文本为向量 (N, dim)."""
        ...

    @property
    def provider(self) -> str:
        """活跃的执行后端名称."""
        return "unknown"


def _load_tokenizer(tokenizer_path: str):
    """Load tokenizer from path. Tries transformers, falls back to tokenizers."""
    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)
    except ImportError:
        pass

    try:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(str(Path(tokenizer_path) / "tokenizer.json"))
        # Wrap in a minimal interface compatible with how we use it
        class _SimpleTokenizer:
            def __init__(self, tok):
                self._tok = tok
                self.pad_token_id: int = tok.token_to_id("[PAD]") or 0
                self.cls_token_id: int = tok.token_to_id("[CLS]") or 101
                self.sep_token_id: int = tok.token_to_id("[SEP]") or 102
                self.model_max_length: int = 512

            def __call__(self, texts: Union[str, list[str]],
                         padding: Union[bool, str] = True,
                         truncation: bool = True,
                         max_length: int = 512,
                         return_tensors: Any = None) -> dict[str, Any]:
                if isinstance(texts, str):
                    texts = [texts]
                encodings = [self._tok.encode(t) for t in texts]
                max_len = min(
                    max(len(e.ids) for e in encodings),
                    max_length or 512
                )
                # Pad/truncate
                input_ids: list[list[int]] = []
                attention_mask: list[list[int]] = []
                for enc in encodings:
                    ids = enc.ids[:max_len]
                    ids = ids + [self.pad_token_id] * (max_len - len(ids))
                    mask = [1] * min(len(enc.ids), max_len)
                    mask = mask + [0] * (max_len - len(mask))
                    input_ids.append(ids)
                    attention_mask.append(mask)

                result: dict[str, Any] = {
                    "input_ids": np.array(input_ids, dtype=np.int64),
                    "attention_mask": np.array(attention_mask, dtype=np.int64),
                }
                # Wrap in a dict-like that also supports attribute access
                class _Batch:
                    __slots__ = ("input_ids", "attention_mask")
                    def __init__(self):
                        self.input_ids: Any = None
                        self.attention_mask: Any = None
                batch = _Batch()
                batch.input_ids = result["input_ids"]
                batch.attention_mask = result["attention_mask"]
                result["_batch"] = batch  # type: ignore[assignment]
                return result
        return _SimpleTokenizer(tok)
    except ImportError:
        raise ImportError(
            "Need either 'transformers' or 'tokenizers' package to load tokenizer. "
            "Install: pip install transformers"
        )


class Embedder(BaseEmbedder):
    """Text embedding using ONNX Runtime with DirectML/CPU support.

    并发安全说明：
    - 单个 ONNX Session 非线程安全。每个 Embedder 实例绑定一个 session。
    - MCP 层通过 asyncio.to_thread() + ThreadPoolExecutor 串行化 GPU 推理。
    - 如需更高并发，创建多个 Embedder 实例（每个实例一个 session）。
    - intra_op_num_threads 控制单个推理内部的并行度。
    - inter_op_num_threads 控制计算图节点间的并行度。
    """

    def __init__(self, model_path: str, tokenizer_path: str,
                 provider: str = "DirectML",
                 intra_op_threads: int = 0,
                 inter_op_threads: int = 0):
        """
        Initialize embedder.

        Args:
            model_path: Path to model.onnx
            tokenizer_path: Path to tokenizer directory
            provider: "DirectML" or "CPUExecutionProvider"
            intra_op_threads: 单个算子的并行线程数 (0=自动)
            inter_op_threads: 计算图节点并行线程数 (0=自动)
        """
        import onnxruntime as ort
        import os

        self._model_path = model_path
        self._tokenizer_path = tokenizer_path
        self._tokenizer = _load_tokenizer(tokenizer_path)
        self._max_length = getattr(
            self._tokenizer, 'model_max_length', 512
        )
        if self._max_length is None or self._max_length > 1000000:
            self._max_length = 512
            try:
                self._tokenizer.model_max_length = 512
            except Exception:
                pass

        # ── 自动检测最优线程数 ──
        cpu_count = os.cpu_count() or 4
        if intra_op_threads <= 0:
            intra_op_threads = max(2, cpu_count // 2)  # 使用一半核心
        if inter_op_threads <= 0:
            inter_op_threads = 1  # 默认串行执行计算图

        self._intra_op_threads = intra_op_threads
        self._inter_op_threads = inter_op_threads

        # Try DirectML first, fall back to CPU
        self._active_provider = "CPUExecutionProvider"
        providers = []

        if provider.lower() in ("directml", "dml"):
            try:
                available = ort.get_available_providers()
                if "DmlExecutionProvider" not in available:
                    print("[naskb] DirectML not available, falling back to CPU")
                else:
                    providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                    print("[naskb] DirectML provider available")
            except Exception:
                print("[naskb] DirectML init failed, falling back to CPU")

        if "CPUExecutionProvider" not in providers:
            providers.append("CPUExecutionProvider")

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = intra_op_threads
        sess_options.inter_op_num_threads = inter_op_threads
        # 启用内存优化
        sess_options.enable_mem_pattern = True
        sess_options.enable_cpu_mem_arena = True

        print(f"[naskb] ONNX threads: intra_op={intra_op_threads}, "
              f"inter_op={inter_op_threads}, provider={providers[0]}")

        try:
            self._session = ort.InferenceSession(
                model_path, sess_options=sess_options,
                providers=providers,
            )
            self._active_provider = self._session.get_providers()[0]
            print(f"[naskb] Embedder initialized with provider: {self._active_provider}")
        except Exception as e:
            # Last resort: CPU only
            print(f"[naskb] GPU session failed ({e}), retrying with CPU only...")
            self._session = ort.InferenceSession(
                model_path, sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )
            self._active_provider = "CPUExecutionProvider"
            print("[naskb] Embedder running on CPU.")

        # Determine output dimension
        self._dim = self._session.get_outputs()[0].shape[-1]

    @property
    def dim(self) -> int:
        """Vector dimension (768 or 1024)."""
        return self._dim

    @property
    def provider(self) -> str:
        """Active execution provider name."""
        return self._active_provider

    def encode(self, text: str) -> np.ndarray:
        """Encode a single text to a normalized vector of shape (dim,)."""
        if not text or not text.strip():
            return np.zeros(self.dim, dtype=np.float32)

        # For long texts, segment and mean pool
        if len(text) > 2000:
            return self._encode_long(text)

        inputs: Any = self._tokenizer(
            text, padding="max_length", truncation=True,
            max_length=self._max_length, return_tensors="np",
        )

        input_ids: np.ndarray = np.asarray(inputs["input_ids"])
        attention_mask: np.ndarray = np.asarray(inputs["attention_mask"])

        # Ensure correct shape
        if input_ids.ndim == 1:
            input_ids = input_ids.reshape(1, -1)
        if attention_mask.ndim == 1:
            attention_mask = attention_mask.reshape(1, -1)

        outputs: list[np.ndarray] = self._session.run(  # type: ignore[assignment]
            None, {
                "input_ids": input_ids.astype(np.int64),
                "attention_mask": attention_mask.astype(np.int64),
            }
        )
        # outputs[0] shape: (1, seq_len, dim)
        token_embeddings: np.ndarray = np.asarray(outputs[0])
        embedding = _mean_pool(token_embeddings, attention_mask)
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-9)
        return embedding.astype(np.float32)

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Encode multiple texts. Returns (N, dim) array."""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = []
            for text in batch:
                emb = self.encode(text)
                batch_embeddings.append(emb)
            all_embeddings.append(np.stack(batch_embeddings))

        return np.concatenate(all_embeddings, axis=0).astype(np.float32)

    def _encode_long(self, text: str, segment_size: int = 450) -> np.ndarray:
        """Encode long text by segmenting and mean pooling segment vectors."""
        # Split by sentences/paragraphs
        segments: list[str] = []
        current = ""
        for char in text:
            current += char
            if len(current) >= segment_size and char in "。！？\n.!\n?":
                segments.append(current.strip())
                current = ""
        if current.strip():
            segments.append(current.strip())

        if len(segments) <= 1:
            # Still try to encode
            return self.encode(text[:self._max_length * 2])

        embeddings = [self.encode(seg) for seg in segments if seg.strip()]
        if not embeddings:
            return np.zeros(self.dim, dtype=np.float32)

        pooled = np.mean(embeddings, axis=0)
        return pooled / (np.linalg.norm(pooled) + 1e-9)


def _mean_pool(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """Mean pooling with attention mask."""
    # token_embeddings: (batch, seq_len, dim)
    # attention_mask: (batch, seq_len)
    mask = np.expand_dims(attention_mask, axis=-1)  # (batch, seq_len, 1)
    mask = mask.astype(token_embeddings.dtype)
    masked = token_embeddings * mask
    summed = masked.sum(axis=1)  # (batch, dim)
    count = mask.sum(axis=1)  # (batch, 1)
    count = np.maximum(count, 1e-9)
    return (summed / count).squeeze(0)  # (dim,)
