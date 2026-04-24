from __future__ import annotations

"""Compatibility wrapper for the TextifAI Obsidian CLI.

This entrypoint currently resolves to the same active product rail as
``scripts/textifai.py`` and is kept for discoverability and compatibility
with existing commands and docs.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != SCRIPT_DIR]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textifai.obsidian.cli import run_cli


if __name__ == "__main__":
    raise SystemExit(run_cli(repo_root=REPO_ROOT))
