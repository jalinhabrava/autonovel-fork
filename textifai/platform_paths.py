from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath

from vault.schema import slugify


def normalize_user_path(value: str | Path) -> Path:
    if isinstance(value, Path):
        return value.expanduser().resolve()
    text = str(value).strip()
    if _looks_like_windows_path(text):
        return _normalize_windows_path(text)
    return Path(text).expanduser().resolve()


def suggest_default_vault_root(*, project_title: str | None = None) -> Path:
    title = project_title or "TextifAI Project"
    folder = slugify(title).replace("_", "-") or "textifai-project"
    return Path.home() / "Documents" / "TextifAI" / folder


def running_inside_wsl() -> bool:
    return "WSL_DISTRO_NAME" in os.environ or "microsoft" in os.uname().release.casefold()


def _looks_like_windows_path(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value))


def _normalize_windows_path(value: str) -> Path:
    win = PureWindowsPath(value)
    drive = win.drive.rstrip(":").lower()
    parts = [part for part in win.parts[1:] if part not in {"\\", "/"}]
    if os.name == "nt":
        return Path(win)
    return Path("/mnt") / drive / Path(*parts)
