"""Identify the calculation code, dependencies and source inputs behind a run."""

import hashlib
from importlib.metadata import version
from pathlib import Path
import sys

from frtb_engine.config import PROJECT_ROOT


def calculation_fingerprint(root: Path = PROJECT_ROOT) -> str:
    files = [root / "pyproject.toml", root / "data/synthetic/trades.csv",
             root / "data/synthetic/market_data.yaml"]
    files += list((root / "src/frtb_engine").glob("*.py"))
    files += list((root / "scripts").glob("*.py"))
    files += list((root / "config").rglob("*.yaml"))
    digest = hashlib.sha256()
    digest.update(sys.version.encode())
    for package in ("numpy", "pandas", "scipy", "matplotlib", "PyYAML", "xlsxwriter"):
        digest.update(f"{package}={version(package)}\n".encode())
    for path in sorted(files):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
