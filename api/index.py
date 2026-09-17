from __future__ import annotations

import importlib.util
from pathlib import Path


source_path = Path(__file__).resolve().parents[1] / "video donwload.py"
spec = importlib.util.spec_from_file_location("tiktok_downloader", source_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {source_path}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app
