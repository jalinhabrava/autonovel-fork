from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from textifai.bootstrap.contracts import (
    BootstrapResult,
    NormalizationPlan,
    NormalizedArtifactDraft,
    SourceDocumentInventory,
    SourceFragment,
)
from vault.schema import IMPORT_STAGING_DIRS, note_frontmatter


def ensure_import_staging_structure(vault_root: str | Path) -> Path:
    root = Path(vault_root).expanduser().resolve()
    for relative in IMPORT_STAGING_DIRS.values():
        (root / relative).mkdir(parents=True, exist_ok=True)
    return root / IMPORT_STAGING_DIRS["root"]


def write_bootstrap_staging(
    *,
    plan: NormalizationPlan,
    inventory: SourceDocumentInventory,
    source_texts: dict[str, str],
    fragments_by_source: dict[str, list[SourceFragment]],
    warnings: list[str] | None = None,
) -> tuple[list[str], dict[str, int], Path]:
    staging_root = ensure_import_staging_structure(plan.target_vault_root)
    written_paths: list[str] = []
    for draft in plan.drafts:
        path = _write_draft(staging_root, draft)
        written_paths.append(str(path))

    manifest_path = _write_manifest(
        staging_root,
        plan=plan,
        inventory=inventory,
        source_texts=source_texts,
        fragments_by_source=fragments_by_source,
        written_paths=written_paths,
        warnings=warnings or [],
    )
    return written_paths, dict(plan.coverage_summary), manifest_path


def _write_draft(staging_root: Path, draft: NormalizedArtifactDraft) -> Path:
    path = Path(draft.target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path = path.with_name(f"{path.stem}__{draft.draft_id[-6:]}{path.suffix}")
    frontmatter = note_frontmatter(
        draft.artifact_type,
        draft.title,
        status=draft.status,
        slug=draft.slug,
        source_id=draft.provenance.source_id if draft.provenance else None,
        source_path=draft.provenance.source_path if draft.provenance else None,
        source_checksum=draft.provenance.source_checksum if draft.provenance else None,
        source_format=draft.provenance.source_format if draft.provenance else None,
        extraction_mode=draft.provenance.extraction_mode if draft.provenance else None,
        extraction_confidence=draft.provenance.extraction_confidence if draft.provenance else None,
        structural_confidence=draft.provenance.structural_confidence if draft.provenance else None,
        import_mode=draft.provenance.import_mode if draft.provenance else None,
        llm_assisted=draft.provenance.llm_assisted if draft.provenance else None,
        fragment_ids=",".join(draft.provenance.fragment_ids) if draft.provenance else None,
        warnings=",".join(draft.provenance.warnings) if draft.provenance else None,
        loss_risk_flags=",".join(draft.provenance.loss_risk_flags) if draft.provenance else None,
        dominant_language=draft.dominant_language,
        detected_languages=",".join(draft.detected_languages),
    )
    body = [
        frontmatter,
        "",
        f"# {draft.title}",
        "",
        "## Imported Material",
        "",
        draft.body.strip(),
    ]
    if draft.register_signals:
        body.extend(["", "## Observed Register Signals", "", ", ".join(draft.register_signals)])
    if draft.normalization_notes:
        body.extend(["", "## Normalization Notes", "", *[f"- {note}" for note in draft.normalization_notes]])
    path.write_text("\n".join(body).rstrip() + "\n")
    return path


def _write_manifest(
    staging_root: Path,
    *,
    plan: NormalizationPlan,
    inventory: SourceDocumentInventory,
    source_texts: dict[str, str],
    fragments_by_source: dict[str, list[SourceFragment]],
    written_paths: list[str],
    warnings: list[str],
) -> Path:
    manifests_root = staging_root / "_manifests"
    manifests_root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_root / f"{plan.plan_id}.json"
    per_document = []
    for document in inventory.documents:
        fragments = fragments_by_source.get(document.source_id, [])
        text = source_texts.get(document.source_id, "")
        covered = sum(len(fragment.text) for fragment in fragments if any(draft.provenance and draft.provenance.source_id == document.source_id and fragment.fragment_id in draft.provenance.fragment_ids for draft in plan.drafts))
        ambiguous = sum(len(fragment.text) for fragment in fragments if fragment.fragment_id in plan.ambiguous_fragments)
        unmapped = sum(len(fragment.text) for fragment in fragments if fragment.fragment_id in plan.unmapped_fragments)
        per_document.append(
            {
                "source_id": document.source_id,
                "path": document.path,
                "relative_path": document.relative_path,
                "filename": document.filename,
                "dominant_language": document.dominant_language,
                "detected_languages": document.detected_languages,
                "total_chars": len(text),
                "covered_chars": covered,
                "ambiguous_chars": ambiguous,
                "unmapped_chars": unmapped,
                "fragment_reports": [
                    {
                        "fragment_id": fragment.fragment_id,
                        "imported": fragment.fragment_id not in plan.unmapped_fragments,
                        "ambiguous": fragment.fragment_id in plan.ambiguous_fragments,
                        "pending": fragment.fragment_id in plan.unmapped_fragments,
                        "skipped_with_reason": "unmapped" if fragment.fragment_id in plan.unmapped_fragments else ("ambiguous" if fragment.fragment_id in plan.ambiguous_fragments else None),
                    }
                    for fragment in fragments
                ],
            }
        )
    manifest_payload = {
        "plan": asdict(plan),
        "inventory": {
            "source_root": inventory.source_root,
            "total_documents": inventory.total_documents,
            "total_bytes": inventory.total_bytes,
            "detected_working_languages": inventory.detected_working_languages,
            "has_multilingual_material": inventory.has_multilingual_material,
            "warnings": inventory.warnings,
        },
        "per_document": per_document,
        "written_paths": written_paths,
        "warnings": warnings,
    }
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True))
    return manifest_path


def validate_staging_outputs(
    *,
    plan: NormalizationPlan,
    written_paths: list[str],
    manifest_path: Path,
) -> list[str]:
    errors: list[str] = []
    staging_root = Path(plan.target_staging_root).resolve()
    if not manifest_path.exists():
        errors.append(f"Missing manifest: {manifest_path}")
    for path_text in written_paths:
        path = Path(path_text).resolve()
        if not path.exists():
            errors.append(f"Missing staged draft: {path}")
            continue
        if staging_root not in path.parents and path != staging_root:
            errors.append(f"Staged draft escaped staging root: {path}")
    for draft in plan.drafts:
        path = Path(draft.target_path).resolve()
        if staging_root not in path.parents and path != staging_root:
            errors.append(f"Planned draft target escaped staging root: {path}")
    return errors
