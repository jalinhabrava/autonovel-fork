from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from adapters.vault_adapter import VaultProjectAdapter
from adapters.workspace_adapter import WorkspaceProjectAdapter


class ProjectStore:
    """Stable project storage facade backed by a pluggable adapter."""

    def __init__(self, base_dir: str | Path, adapter=None):
        self.base_dir = Path(base_dir)
        self.adapter = adapter or self._adapter_from_env()

    def _adapter_from_env(self):
        backend = os.environ.get("AUTONOVEL_PROJECT_BACKEND", "workspace").strip().lower()
        if backend == "workspace":
            return WorkspaceProjectAdapter(self.base_dir)
        if backend == "vault":
            vault_root = os.environ.get("AUTONOVEL_VAULT_ROOT", "").strip()
            if not vault_root:
                raise ValueError("AUTONOVEL_VAULT_ROOT must be set when AUTONOVEL_PROJECT_BACKEND=vault")
            return VaultProjectAdapter(vault_root)
        raise ValueError(f"Unsupported AUTONOVEL_PROJECT_BACKEND={backend!r}")

    @property
    def chapters_dir(self) -> Path:
        return self.adapter.chapters_dir

    @property
    def briefs_dir(self) -> Path:
        return self.adapter.briefs_dir

    @property
    def edit_logs_dir(self) -> Path:
        return self.adapter.edit_logs_dir

    @property
    def eval_logs_dir(self) -> Path:
        return self.adapter.eval_logs_dir

    def ensure_runtime_dirs(self):
        self.adapter.ensure_runtime_dirs()

    def path(self, relative_path: str | Path) -> Path:
        return self.adapter.resolve(relative_path)

    def artifact_path(self, artifact_name: str) -> Path:
        return self.adapter.artifact_path(artifact_name)

    def read_text(self, relative_path: str | Path, default: str = "") -> str:
        path = self.path(relative_path)
        try:
            return path.read_text()
        except FileNotFoundError:
            return default

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        path = self.path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def read_artifact(self, artifact_name: str, default: str = "") -> str:
        if hasattr(self.adapter, "read_artifact"):
            return self.adapter.read_artifact(artifact_name, default)
        try:
            return self.artifact_path(artifact_name).read_text()
        except FileNotFoundError:
            return default

    def write_artifact(self, artifact_name: str, content: str) -> Path:
        if hasattr(self.adapter, "write_artifact"):
            return self.adapter.write_artifact(artifact_name, content)
        path = self.artifact_path(artifact_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def read_seed(self) -> str:
        return self.read_artifact("seed")

    def read_voice(self) -> str:
        return self.read_artifact("voice")

    def read_world(self) -> str:
        return self.read_artifact("world")

    def read_characters(self) -> str:
        return self.read_artifact("characters")

    def read_canon(self) -> str:
        return self.read_artifact("canon")

    def read_outline(self) -> str:
        return self.read_artifact("outline")

    def read_arc_summary(self) -> str:
        return self.read_artifact("arc_summary")

    def read_mystery(self) -> str:
        return self.read_artifact("mystery")

    def read_state(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if hasattr(self.adapter, "read_state"):
            return self.adapter.read_state(default)
        path = self.artifact_path("state")
        if not path.exists():
            return dict(default or {})
        with path.open() as f:
            return json.load(f)

    def write_state(self, state: dict[str, Any]) -> Path:
        if hasattr(self.adapter, "write_state"):
            return self.adapter.write_state(state)
        path = self.artifact_path("state")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))
        return path

    def append_result_row(
        self,
        *,
        commit: str,
        phase: str,
        score,
        word_count: int,
        status: str,
        description: str,
    ) -> Path:
        if hasattr(self.adapter, "append_result_row"):
            return self.adapter.append_result_row(
                commit=commit,
                phase=phase,
                score=score,
                word_count=word_count,
                status=status,
                description=description,
            )
        path = self.artifact_path("results")
        header = "commit\tphase\tscore\tword_count\tstatus\tdescription\n"
        if not path.exists() or path.stat().st_size == 0:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(header)
        with path.open("a") as f:
            f.write(f"{commit}\t{phase}\t{score}\t{word_count}\t{status}\t{description}\n")
        return path

    def chapter_path(self, chapter_num: int) -> Path:
        return self.adapter.chapter_path(chapter_num)

    def read_chapter(self, chapter_num: int, default: str = "") -> str:
        try:
            return self.chapter_path(chapter_num).read_text()
        except FileNotFoundError:
            return default

    def write_chapter(self, chapter_num: int, content: str) -> Path:
        path = self.chapter_path(chapter_num)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def list_chapter_paths(self) -> list[Path]:
        return self.adapter.list_chapter_paths()

    def count_chapters(self) -> int:
        return len(self.list_chapter_paths())

    def count_words_in_chapters(self) -> int:
        return sum(len(path.read_text().split()) for path in self.list_chapter_paths())

    def brief_path(self, name: str) -> Path:
        return self.adapter.briefs_dir / name

    def list_brief_paths(self, pattern: str = "*.md") -> list[Path]:
        return sorted(self.adapter.briefs_dir.glob(pattern))

    def edit_log_path(self, name: str) -> Path:
        return self.adapter.edit_logs_dir / name

    def list_edit_log_paths(self, pattern: str) -> list[Path]:
        return sorted(self.adapter.edit_logs_dir.glob(pattern))

    def eval_log_path(self, name: str) -> Path:
        return self.adapter.eval_logs_dir / name

    def get_title(self, default: str = "Untitled Novel") -> str:
        outline = self.artifact_path("outline")
        if outline.exists():
            first_line = outline.read_text().splitlines()
            if first_line:
                title = first_line[0].lstrip("# ").strip()
                if title:
                    return title

        ch1 = self.chapter_path(1)
        if ch1.exists():
            first_line = ch1.read_text().splitlines()
            if first_line:
                title = first_line[0].lstrip("# ").strip()
                if title:
                    return title

        return default
