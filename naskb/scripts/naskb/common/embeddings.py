"""文本嵌入 — ONNX bge-small-zh（本地 CPU，无 torch/transformers 依赖）。

用于语义向量检索（desc search/ask 的向量路径）。
模型：Xenova/bge-small-zh-v1.5（int8 量化，~24MB），
下载到工作区 models/bge-small-zh-v1.5/（首次自动下载）。
"""
from __future__ import annotations

import json
import math
import os
from typing import Optional

import numpy as np

MODEL_NAME = "bge-small-zh-v1.5"
MODEL_DIR = "models"                       # 工作区下
DIM = 512                                  # bge-small-zh 维度
_HF_ROOT = "https://huggingface.co/Xenova/bge-small-zh-v1.5/resolve/main/"
_HF_FILES = {
    "onnx/model_quantized.onnx": "model.onnx",
    "tokenizer.json": "tokenizer.json",
    "config.json": "config.json",
    "special_tokens_map.json": "special_tokens_map.json",
}


def ensure_model(work_path: str) -> str:
    """确保模型已下载（工作区 models/bge-small-zh-v1.5/），返回目录路径。"""
    model_dir = os.path.join(work_path, MODEL_DIR, MODEL_NAME)
    model_file = os.path.join(model_dir, "model.onnx")
    if os.path.isfile(model_file) and os.path.getsize(model_file) > 100_000:
        return model_dir
    import httpx
    os.makedirs(model_dir, exist_ok=True)
    for src, dst in _HF_FILES.items():
        p = os.path.join(model_dir, dst)
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            continue
        with httpx.Client(follow_redirects=True, timeout=180) as c:
            r = c.get(_HF_ROOT + src)
            r.raise_for_status()
            with open(p, "wb") as f:
                f.write(r.content)
    return model_dir


def model_ready(work_path: str) -> bool:
    """模型是否已下载（快速存在性检查，不触发联网下载）。

    读路径（search/ask/serve/MCP 检索内核）用它先判定：模型缺失时直接
    回退 BM25，而不是静默发起 180s×N 的下载阻塞——下载只由显式的
    index-vectors / kb_index_vectors 触发。
    """
    model_file = os.path.join(work_path, MODEL_DIR, MODEL_NAME, "model.onnx")
    return os.path.isfile(model_file) and os.path.getsize(model_file) > 100_000


class Embedder:
    """bge-small-zh ONNX 嵌入器：tokenize → CLS embedding → L2 归一化。"""

    def __init__(self, work_path: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = ensure_model(work_path)
        self._tok = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
        self._tok.enable_truncation(max_length=512)
        self._tok.enable_padding(pad_id=0, pad_token="[PAD]")
        so = ort.SessionOptions()
        so.log_severity_level = 3
        self._session = ort.InferenceSession(
            os.path.join(model_dir, "model.onnx"), sess_options=so,
            providers=["CPUExecutionProvider"])
        self._inputs = [i.name for i in self._session.get_inputs()]
        self._output = self._session.get_outputs()[0].name

    def encode(self, texts: list[str]) -> np.ndarray:
        """批量编码，返回 (N, DIM) 已归一化向量。"""
        enc = self._tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed: dict[str, np.ndarray] = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        out = self._session.run([self._output], feed)[0]
        # bge-zh 使用 CLS token 的表示（输出 shape: (N, seq, dim)）
        vecs = out[:, 0, :]
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.maximum(norms, 1e-12)

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]

    def close(self):
        try:
            del self._session
        except Exception:
            pass
