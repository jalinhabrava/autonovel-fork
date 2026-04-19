from __future__ import annotations

import json
import ast
from pathlib import Path

from vault.schema import ROOT_NOTES, VAULT_DIRS, slugify


class VaultProjectAdapter:
    """Obsidian-vault-backed adapter for narrative project storage."""

    def __init__(self, vault_root: str | Path):
        self.vault_root = Path(vault_root)
        self.chapters_dir = self.vault_root / VAULT_DIRS["chapters"]
        self.briefs_dir = self.vault_root / VAULT_DIRS["editorial_briefs"]
        self.edit_logs_dir = self.vault_root / VAULT_DIRS["editorial_logs"]
        self.eval_logs_dir = self.vault_root / VAULT_DIRS["editorial_eval"]
        self.world_lore_dir = self.vault_root / VAULT_DIRS["world_lore"]
        self.character_profiles_dir = self.vault_root / VAULT_DIRS["character_profiles"]
        self.outline_scenes_dir = self.vault_root / VAULT_DIRS["outline_scenes"]
        self.canon_decisions_dir = self.vault_root / VAULT_DIRS["canon_decisions"]
        self.review_dir = self.vault_root / VAULT_DIRS["editorial_reviews"]
        self.reader_panel_dir = self.vault_root / VAULT_DIRS["editorial_reader_panel"]

    def resolve(self, relative_path: str | Path) -> Path:
        return self.vault_root / relative_path

    def artifact_path(self, artifact_name: str) -> Path:
        try:
            relative = ROOT_NOTES[artifact_name]
        except KeyError as exc:
            raise KeyError(f"Unknown vault artifact: {artifact_name}") from exc
        return self.resolve(relative)

    def chapter_path(self, chapter_num: int) -> Path:
        return self.chapters_dir / f"ch_{chapter_num:02d}.md"

    def list_chapter_paths(self) -> list[Path]:
        if not self.chapters_dir.exists():
            return []
        return sorted(self.chapters_dir.glob("ch_*.md"))

    def ensure_runtime_dirs(self):
        for relative_dir in VAULT_DIRS.values():
            (self.vault_root / relative_dir).mkdir(parents=True, exist_ok=True)
        (self.vault_root / ".obsidian").mkdir(exist_ok=True)

    def note_path(self, note_type: str, slug: str) -> Path:
        slug = slugify(slug)
        mapping = {
            "character": self.character_profiles_dir,
            "lore": self.world_lore_dir,
            "scene": self.outline_scenes_dir,
            "decision": self.canon_decisions_dir,
            "chapter": self.chapters_dir,
            "revision_brief": self.briefs_dir,
            "review": self.review_dir,
            "reader_panel": self.reader_panel_dir,
        }
        try:
            directory = mapping[note_type]
        except KeyError as exc:
            raise KeyError(f"Unsupported vault note type: {note_type}") from exc
        return directory / f"{slug}.md"

    def read_artifact(self, artifact_name: str, default: str = "") -> str:
        root_path = self.artifact_path(artifact_name)
        root_text = root_path.read_text() if root_path.exists() else default

        if artifact_name == "world":
            return self._combine_notes(root_text, "Lore Notes", self.world_lore_dir)
        if artifact_name == "characters":
            return self._combine_notes(root_text, "Character Notes", self.character_profiles_dir)
        if artifact_name == "outline":
            return self._combine_notes(root_text, "Scene Notes", self.outline_scenes_dir)
        if artifact_name == "canon":
            return self._combine_notes(root_text, "Canon Decisions", self.canon_decisions_dir)
        return root_text

    def write_artifact(self, artifact_name: str, content: str) -> Path:
        path = self.artifact_path(artifact_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def read_state(self, default: dict | None = None) -> dict:
        path = self.artifact_path("state")
        if not path.exists():
            return dict(default or {})
        with path.open() as f:
            return json.load(f)

    def write_state(self, state: dict) -> Path:
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
        path = self.artifact_path("results")
        header = "commit\tphase\tscore\tword_count\tstatus\tdescription\n"
        if not path.exists() or path.stat().st_size == 0:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(header)
        with path.open("a") as f:
            f.write(f"{commit}\t{phase}\t{score}\t{word_count}\t{status}\t{description}\n")
        return path

    def _combine_notes(self, root_text: str, heading: str, directory: Path) -> str:
        notes = []
        if directory.exists():
            for path in sorted(directory.glob("*.md")):
                text = path.read_text().strip()
                status = self._read_frontmatter_value(text, "status") or "proposed"
                if status in {"rejected", "superseded"}:
                    continue
                title = self._read_frontmatter_value(text, "title") or path.stem.replace("_", " ")
                body = self._strip_frontmatter(text)
                notes.append(f"### [{status}] {title}\n\n{body.strip()}")

        if not notes:
            return root_text
        root = root_text.strip()
        suffix = f"## {heading}\n\n" + "\n\n".join(notes)
        return f"{root}\n\n{suffix}".strip() + "\n"

    def _read_frontmatter_value(self, text: str, key: str) -> str | None:
        if not text.startswith("---\n"):
            return None
        lines = text.splitlines()
        try:
            closing = lines[1:].index("---") + 1
        except ValueError:
            return None
        for line in lines[1:closing]:
            if line.startswith(f"{key}:"):
                value = line.split(":", 1)[1].strip()
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    try:
                        parsed = ast.literal_eval(value)
                    except (ValueError, SyntaxError):
                        return value[1:-1]
                    return str(parsed)
                return value
        return None

    def _strip_frontmatter(self, text: str) -> str:
        if not text.startswith("---\n"):
            return text
        lines = text.splitlines()
        try:
            closing = lines[1:].index("---") + 1
        except ValueError:
            return text
        return "\n".join(lines[closing + 1:]).lstrip()
