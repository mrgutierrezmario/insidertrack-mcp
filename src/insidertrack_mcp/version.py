"""The package version, read from the ``VERSION`` file at the repository root."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    __version__ = version("insidertrack-mcp")
except PackageNotFoundError:  # running from a checkout without installing
    _file = Path(__file__).resolve().parents[2] / "VERSION"
    __version__ = _file.read_text().strip() if _file.exists() else "0.0.0"
