"""ONNX model download and caching for NASKB.

支持 HuggingFace 官方源和镜像源（如 hf-mirror.com）。
设置环境变量 HF_ENDPOINT 或 config.toml 中的 hf_endpoint 切换镜像。
"""
import os
import shutil
import time
from pathlib import Path
from typing import Optional


class ModelManager:
    """Manages ONNX embedding model lifecycle."""

    # Known HuggingFace model repos for BGE series
    HF_MODELS = {
        "bge-base-zh-v1.5": "BAAI/bge-base-zh-v1.5",
        "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
    }

    # 模型文件大小预估 (用于进度估算)
    _MODEL_SIZES = {
        "bge-base-zh-v1.5": {"total_mb": 420, "files": 5},
        "bge-large-zh-v1.5": {"total_mb": 1300, "files": 5},
    }

    @staticmethod
    def _setup_mirror(endpoint: str = "") -> None:
        """配置 HuggingFace 镜像端点。"""
        if endpoint:
            os.environ["HF_ENDPOINT"] = endpoint
            print(f"[naskb] Using HF mirror: {endpoint}")

    @staticmethod
    def ensure_model(work_path: str, model_name: str,
                     hf_endpoint: str = "") -> tuple[str, str]:
        """
        Ensure ONNX model and tokenizer are available.

        Args:
            work_path: 工作路径
            model_name: 模型名称
            hf_endpoint: HF 镜像地址 (如 https://hf-mirror.com)

        Returns:
            (model_path, tokenizer_path)
        """
        import os
        # 优先使用传入的 endpoint，其次环境变量
        endpoint = hf_endpoint or os.environ.get("HF_ENDPOINT", "")
        if endpoint:
            ModelManager._setup_mirror(endpoint)

        target_dir = Path(work_path) / "models" / model_name
        target_dir.mkdir(parents=True, exist_ok=True)

        model_path = target_dir / "model.onnx"
        tokenizer_dir = target_dir

        if model_path.exists() and (tokenizer_dir / "tokenizer.json").exists():
            print(f"[naskb] Model {model_name} already cached at {target_dir}")
            return str(model_path), str(tokenizer_dir)

        info = ModelManager._MODEL_SIZES.get(model_name, {"total_mb": 500, "files": 5})
        print(f"[naskb] Downloading model {model_name} (~{info['total_mb']}MB)...")
        print(f"[naskb] Source: {endpoint or 'HuggingFace Hub'}")

        t0 = time.time()
        try:
            ModelManager._download_model(model_name, str(target_dir))
            elapsed = time.time() - t0
            print(f"[naskb] Download complete in {elapsed:.1f}s.")
        except Exception as e:
            print(f"[naskb] Auto-download failed: {e}")
            if not endpoint:
                print(f"[naskb] Tip: Set HF_ENDPOINT=https://hf-mirror.com for faster download in some regions")
            print(f"[naskb] Manual: place model files in {target_dir}")
            print(f"[naskb] Required: model.onnx, tokenizer.json, tokenizer_config.json, special_tokens_map.json")
            raise

        return str(model_path), str(tokenizer_dir)

    @staticmethod
    def _download_model(model_name: str, target_dir: str) -> None:
        """Download tokenizer and model files from HuggingFace Hub."""
        from huggingface_hub import hf_hub_download, list_repo_files

        hf_name = ModelManager.HF_MODELS.get(model_name, model_name)

        # 1. Download tokenizer files
        tokenizer_files = [
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "sentencepiece.bpe.model",
        ]

        for fname in tokenizer_files:
            try:
                hf_hub_download(
                    repo_id=hf_name,
                    filename=fname,
                    local_dir=target_dir,
                    local_dir_use_symlinks=False,
                )
            except Exception:
                pass  # Not all models have all files

        # 2. Try to get ONNX model
        # Some HF repos have pre-exported ONNX models
        try:
            repo_files = list_repo_files(hf_name)
            onnx_files = [f for f in repo_files if f.endswith(".onnx")]
            if onnx_files:
                for onnx_file in onnx_files[:1]:
                    hf_hub_download(
                        repo_id=hf_name,
                        filename=onnx_file,
                        local_dir=target_dir,
                        local_dir_use_symlinks=False,
                    )
                    # Rename to model.onnx if needed
                    src = Path(target_dir) / onnx_file
                    dst = Path(target_dir) / "model.onnx"
                    if src != dst:
                        shutil.move(str(src), str(dst))
                print(f"[naskb] Downloaded pre-exported ONNX model.")
                return
        except Exception:
            pass

        # 3. Export ONNX locally (requires optimum + torch)
        print("[naskb] No pre-exported ONNX found. Attempting local export...")
        try:
            ModelManager._export_onnx(model_name, target_dir, hf_name)
        except ImportError:
            raise RuntimeError(
                "Cannot export model. Install dev dependencies:\n"
                "  pip install optimum[onnxruntime] transformers torch"
            )

    @staticmethod
    def _export_onnx(model_name: str, target_dir: str, hf_name: str) -> None:
        """Export a HuggingFace model to ONNX format (opset 14 for DirectML compatibility)."""
        import torch
        import torch.nn as nn
        from transformers import AutoTokenizer, AutoModel
        import numpy as np

        print(f"[naskb] Loading {hf_name} for ONNX export...")

        tokenizer = AutoTokenizer.from_pretrained(hf_name, trust_remote_code=True)
        base_model = AutoModel.from_pretrained(hf_name, trust_remote_code=True)
        base_model.eval()

        # Create a wrapper to avoid transformers' complex forward signature
        # This enables legacy TorchScript export at opset 14 for DirectML compatibility
        class BGEEncoder(nn.Module):
            def __init__(self, model):
                super().__init__()
                self.embeddings = model.embeddings
                self.encoder = model.encoder
                self.num_layers = len(model.encoder.layer)

            def forward(self, input_ids, attention_mask):
                extended_attention_mask = attention_mask.unsqueeze(1).unsqueeze(2)
                extended_attention_mask = (1.0 - extended_attention_mask.float()) * -10000.0
                embedding_output = self.embeddings(input_ids=input_ids)
                encoder_outputs = self.encoder(
                    embedding_output,
                    attention_mask=extended_attention_mask,
                    head_mask=[None] * self.num_layers,
                    output_attentions=False,
                    output_hidden_states=False,
                    return_dict=False,
                )
                return encoder_outputs[0]

        export_model = BGEEncoder(base_model)
        export_model.eval()

        # Save tokenizer
        tokenizer.save_pretrained(target_dir)

        # Export to ONNX at opset 14 (DirectML max supported opset)
        dummy = tokenizer(
            "测试文本", return_tensors="pt",
            padding="max_length", max_length=512, truncation=True,
        )

        onnx_path = Path(target_dir) / "model.onnx"
        torch.onnx.export(
            export_model,
            (dummy["input_ids"], dummy["attention_mask"]),
            str(onnx_path),
            input_names=["input_ids", "attention_mask"],
            output_names=["last_hidden_state"],
            dynamic_axes={
                "input_ids": {0: "batch_size", 1: "sequence_length"},
                "attention_mask": {0: "batch_size", 1: "sequence_length"},
                "last_hidden_state": {0: "batch_size", 1: "sequence_length"},
            },
            opset_version=14,
            do_constant_folding=True,
            dynamo=False,  # Legacy exporter for DirectML compatibility
        )
        print(f"[naskb] ONNX model (opset 14, DirectML compatible) exported to {onnx_path}")


def download_model_cli(work_path: str, model_name: str) -> None:
    """CLI entry point for model download."""
    ModelManager.ensure_model(work_path, model_name)
