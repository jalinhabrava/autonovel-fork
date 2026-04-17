from __future__ import annotations

from pathlib import Path


class WorkspaceProjectAdapter:
    """Adapter for the classic AutoNovel workspace layout."""

    ARTIFACT_PATHS = {
        "seed": "seed.txt",
        "voice": "voice.md",
        "world": "world.md",
        "characters": "characters.md",
        "canon": "canon.md",
        "outline": "outline.md",
        "mystery": "MYSTERY.md",
        "arc_summary": "arc_summary.md",
        "manuscript": "manuscript.md",
        "state": "state.json",
        "results": "results.tsv",
    }

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.chapters_dir = self.base_dir / "chapters"
        self.briefs_dir = self.base_dir / "briefs"
        self.edit_logs_dir = self.base_dir / "edit_logs"
        self.eval_logs_dir = self.base_dir / "eval_logs"

    def resolve(self, relative_path: str | Path) -> Path:
        return self.base_dir / relative_path

    def artifact_path(self, artifact_name: str) -> Path:
        try:
            relative = self.ARTIFACT_PATHS[artifact_name]
        except KeyError as exc:
            raise KeyError(f"Unknown project artifact: {artifact_name}") from exc
        return self.resolve(relative)

    def chapter_path(self, chapter_num: int) -> Path:
        return self.chapters_dir / f"ch_{chapter_num:02d}.md"

    def list_chapter_paths(self) -> list[Path]:
        if not self.chapters_dir.exists():
            return []
        return sorted(self.chapters_dir.glob("ch_*.md"))

    def ensure_runtime_dirs(self):
        self.chapters_dir.mkdir(exist_ok=True)
        self.briefs_dir.mkdir(exist_ok=True)
        self.edit_logs_dir.mkdir(exist_ok=True)
        self.eval_logs_dir.mkdir(exist_ok=True)
