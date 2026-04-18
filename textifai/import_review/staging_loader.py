from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from interactive.query import parse_frontmatter, strip_frontmatter
from textifai.bootstrap.contracts import ImportProvenance
from textifai.import_review.contracts import ExtractionProfile
from textifai.import_review.extraction import extraction_profile_from_metadata
from vault.schema import IMPORT_STAGING_DIRS


@dataclass(frozen=True)
class LoadedStagedDraft:
    draft_id: str
    staging_path: str
    body: str
    frontmatter: dict[str, str] = field(default_factory=dict)
    manifest_draft: dict = field(default_factory=dict)
    provenance: ImportProvenance | None = None
    extraction_profile: ExtractionProfile | None = None
    artifact_type: str = "mixed_note"
    target_slug: str = ""
    target_path: str = ""
    source_format: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StagingImportBundle:
    vault_root: str
    staging_root: str
    manifest_path: str
    manifest: dict
    coverage_summary: dict[str, int]
    drafts: list[LoadedStagedDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_staging_import_bundle(vault_root: str | Path, plan_id: str | None = None) -> StagingImportBundle:
    vault_root = Path(vault_root).expanduser().resolve()
    staging_root = vault_root / IMPORT_STAGING_DIRS["root"]
    manifests_root = staging_root / "_manifests"
    if not manifests_root.exists():
        raise FileNotFoundError(f"Missing import staging manifests directory: {manifests_root}")
    manifest_path = _resolve_manifest_path(manifests_root, plan_id)
    manifest = json.loads(manifest_path.read_text())
    plan = manifest.get("plan", {})
    drafts = [
        _load_staged_draft(staging_root, draft_entry)
        for draft_entry in plan.get("drafts", [])
    ]
    coverage_summary = dict(plan.get("coverage_summary", {}))
    warnings = list(manifest.get("warnings", []))
    return StagingImportBundle(
        vault_root=str(vault_root),
        staging_root=str(staging_root),
        manifest_path=str(manifest_path),
        manifest=manifest,
        coverage_summary=coverage_summary,
        drafts=drafts,
        warnings=warnings,
    )


def _resolve_manifest_path(manifests_root: Path, plan_id: str | None) -> Path:
    if plan_id:
        path = manifests_root / f"{plan_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing manifest for plan {plan_id}: {path}")
        return path
    manifests = sorted(manifests_root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        raise FileNotFoundError(f"No import staging manifests found in {manifests_root}")
    return manifests[0]


def _load_staged_draft(staging_root: Path, draft_entry: dict) -> LoadedStagedDraft:
    target_path = Path(str(draft_entry.get("target_path") or ""))
    if not target_path.is_absolute():
        target_path = (staging_root / target_path).resolve()
    text = target_path.read_text()
    frontmatter = parse_frontmatter(text)
    body = strip_frontmatter(text)
    provenance_dict = draft_entry.get("provenance") or {}
    provenance = None
    if isinstance(provenance_dict, dict) and provenance_dict:
        provenance = ImportProvenance(
            source_id=str(provenance_dict.get("source_id") or draft_entry.get("draft_id") or target_path.stem),
            source_path=str(provenance_dict.get("source_path") or ""),
            source_checksum=str(provenance_dict.get("source_checksum") or ""),
            source_format=str(provenance_dict.get("source_format") or frontmatter.get("source_format") or target_path.suffix.lstrip(".") or "md"),
            extraction_mode=str(provenance_dict.get("extraction_mode") or frontmatter.get("extraction_mode") or "native_text"),
            extraction_confidence=_coerce_float(provenance_dict.get("extraction_confidence") or frontmatter.get("extraction_confidence") or 1.0),
            structural_confidence=_coerce_float(provenance_dict.get("structural_confidence") or frontmatter.get("structural_confidence") or 1.0),
            fragment_ids=[str(value) for value in provenance_dict.get("fragment_ids", [])],
            char_ranges=[dict(item) for item in provenance_dict.get("char_ranges", []) if isinstance(item, dict)],
            import_mode=str(provenance_dict.get("import_mode") or "literal_copy"),
            llm_assisted=bool(provenance_dict.get("llm_assisted", False)),
            warnings=[str(value) for value in provenance_dict.get("warnings", [])],
            loss_risk_flags=[str(value) for value in provenance_dict.get("loss_risk_flags", [])],
            notes=[str(value) for value in provenance_dict.get("notes", [])],
        )
    extraction_profile = extraction_profile_from_metadata(path=target_path, provenance=provenance, frontmatter=frontmatter)
    return LoadedStagedDraft(
        draft_id=str(draft_entry.get("draft_id") or target_path.stem),
        staging_path=str(target_path),
        body=body,
        frontmatter=frontmatter,
        manifest_draft=dict(draft_entry),
        provenance=provenance,
        extraction_profile=extraction_profile,
        artifact_type=str(draft_entry.get("artifact_type") or frontmatter.get("kind") or "mixed_note"),
        target_slug=str(draft_entry.get("slug") or frontmatter.get("slug") or target_path.stem),
        target_path=str(draft_entry.get("target_path") or target_path),
        source_format=extraction_profile.source_format,
        notes=[str(value) for value in draft_entry.get("normalization_notes", [])],
    )


def _coerce_float(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
