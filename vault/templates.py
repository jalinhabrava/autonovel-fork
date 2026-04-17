from __future__ import annotations

from pathlib import Path

from vault.schema import TEMPLATE_ROOT


def load_template(relative_path: str) -> str:
    path = TEMPLATE_ROOT / relative_path
    return path.read_text()


def render_template(relative_path: str, **values) -> str:
    return load_template(relative_path).format(**values)
