"""Environment bootstrap for NASKB.

Creates a self-contained Python virtual environment at the work path,
installs dependencies, and downloads the embedding model.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


class Bootstrap:
    """Ensures the NASKB work environment is ready."""

    @staticmethod
    def ensure(work_path: str, skill_home: str | None = None) -> str:
        """
        Ensure the work environment is ready.
        Returns path to the Python executable inside the venv.

        Steps:
        1. Create work_path if not exists
        2. Create .venv if not exists
        3. Create config.toml template if not exists
        4. Install dependencies into .venv
        """
        wp = Path(work_path).resolve()
        wp.mkdir(parents=True, exist_ok=True)

        venv_dir = wp / ".venv"
        if skill_home is None:
            # Try to find skill home relative to this file
            skill_home = str(Path(__file__).resolve().parent.parent)

        # Determine venv Python path
        if sys.platform == "win32":
            venv_python = str(venv_dir / "Scripts" / "python.exe")
        else:
            venv_python = str(venv_dir / "bin" / "python")

        # Create venv if needed
        if not Path(venv_python).exists():
            print(f"[naskb] Creating virtual environment at {venv_dir}...")
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir), "--clear"],
                check=True, capture_output=True,
            )
            print("[naskb] Virtual environment created.")

        # Create default config if not exists
        config_file = wp / "config.toml"
        if not config_file.exists():
            Bootstrap.create_default_config(str(wp))

        # Install dependencies
        Bootstrap.install_deps(venv_python, skill_home)

        return venv_python

    @staticmethod
    def install_deps(venv_python: str, skill_home: str) -> None:
        """Install required packages into the venv."""
        print("[naskb] Installing dependencies (this may take a few minutes)...")

        # Core packages (no PyTorch required at runtime)
        packages = [
            "lancedb",
            "click",
            "fsspec",
            "numpy",
            "onnxruntime-directml",
            "huggingface_hub",
            "tokenizers",
        ]

        # Also install transformers (for tokenizer only, not model weights)
        packages.append("transformers")

        cmd = [venv_python, "-m", "pip", "install", "--upgrade", "pip"]
        subprocess.run(cmd, check=True, capture_output=True)

        cmd = [venv_python, "-m", "pip", "install"] + packages
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # If DirectML fails, try CPU-only onnxruntime
            print("[naskb] DirectML install failed, trying CPU onnxruntime...")
            # Find and replace onnxruntime-directml with onnxruntime in packages
            packages.remove("onnxruntime-directml")
            packages.append("onnxruntime")
            cmd = [venv_python, "-m", "pip", "install"] + packages
            subprocess.run(cmd, check=True, capture_output=True)

        print("[naskb] Dependencies installed.")

    @staticmethod
    def create_default_config(work_path: str, model_name: str = "bge-base-zh-v1.5") -> None:
        """Create a default config.toml template."""
        from .config import Config

        data = {
            "model": {
                "name": model_name,
                "execution_provider": "directml",
                "batch_size": 32,
            },
            "db": {"path": "db/"},
            "state": {"path": "state.db"},
            "sources": [{
                "id": "default",
                "name": "Default",
                "fs_type": "local",
                "root_url": "",
                "enabled": True,
            }],
            "exclusions": {
                "ext": [".exe", ".dll", ".bin", ".iso", ".tmp"],
                "folder": [".git", ".svn", "__pycache__", "node_modules"],
            },
        }
        cfg = Config(work_path, data)
        cfg.save()
        print(f"[naskb] Default config created at {work_path}/config.toml")


def run_in_venv(work_path: str, skill_home: str | None = None) -> int:
    """
    Entry point: ensure venv exists, then run the CLI inside it.
    Returns exit code.
    """
    venv_python = Bootstrap.ensure(work_path, skill_home)

    # Re-run the current script inside the venv
    script = str(Path(skill_home or Path(__file__).resolve().parent.parent) /
                 "naskb" / "cli.py")

    env = os.environ.copy()
    env["NASKB_WORK"] = str(Path(work_path).resolve())
    env["NASKB_HOME"] = str(Path(skill_home or Path(__file__).resolve().parent.parent).resolve())

    result = subprocess.run(
        [venv_python, script] + sys.argv[1:],
        env=env,
    )
    return result.returncode
