from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textifai.bootstrap.contracts import BOOTSTRAP_ARTIFACT_TYPE_CATALOG, SourceDocumentRecord, SourceFragment, VaultInitializationConfig
from textifai.bootstrap.language import build_language_profile
from textifai.bootstrap.segmenter import segment_source_document


@dataclass(frozen=True)
class BootstrapPrompt:
    prompt_version: str
    system_prompt: str
    user_payload: dict[str, Any]
    required_output_schema: dict[str, Any]
    catalogs: dict[str, tuple[str, ...]]


def build_bootstrap_prompt(
    *,
    config: VaultInitializationConfig,
    document: SourceDocumentRecord,
    text: str,
    fragments: list[SourceFragment] | None = None,
) -> BootstrapPrompt:
    prepared_fragments = fragments or segment_source_document(document, text)
    language_profile = build_language_profile(
        inventory=_inventory_stub(config, document),
        fragments_by_source={document.source_id: prepared_fragments},
        source_texts={document.source_id: text},
        project_primary_language=config.primary_language,
        working_languages=config.working_languages,
    )
    source_excerpt = text[:8000]
    return BootstrapPrompt(
        prompt_version="1",
        system_prompt=(
            "You analyze source documents for a conservative TextifAI bootstrap import. "
            "Do not translate, rewrite, summarize, or invent structure. "
            "Return only JSON. Preserve fidelity and mark uncertainty explicitly."
        ),
        user_payload={
            "config": {
                "mode": config.mode,
                "project_title": config.project_title,
                "primary_language": config.primary_language,
                "working_languages": config.working_languages,
            },
            "document": {
                "source_id": document.source_id,
                "path": document.path,
                "relative_path": document.relative_path,
                "filename": document.filename,
                "dominant_language": document.dominant_language,
                "detected_languages": document.detected_languages,
                "has_mixed_language": document.has_mixed_language,
                "likely_content_kinds": document.likely_content_kinds,
            },
            "language_profile": {
                "project_primary_language": language_profile.project_primary_language,
                "working_languages": language_profile.working_languages,
                "document_languages": language_profile.document_languages.get(document.source_id, []),
                "has_multilingual_documents": language_profile.has_multilingual_documents,
            },
            "source_excerpt": source_excerpt,
            "fragments": [
                {
                    "fragment_id": fragment.fragment_id,
                    "char_start": fragment.char_start,
                    "char_end": fragment.char_end,
                    "text": fragment.text[:2000],
                    "detected_kind": fragment.detected_kind,
                    "kind_confidence": fragment.kind_confidence,
                    "language": fragment.language,
                    "has_mixed_language": fragment.has_mixed_language,
                    "register_signals": fragment.register_signals,
                }
                for fragment in prepared_fragments
            ],
            "analysis_targets": [
                "detect_primary_language",
                "detect_secondary_languages",
                "classify_fragments",
                "flag_ambiguous_material",
                "identify_article_or_note_like_sections",
                "suggest_conservative_artifact_types",
                "preserve_literal_text",
            ],
        },
        required_output_schema={
            "dominant_language": "string|null",
            "detected_languages": ["string"],
            "has_mixed_language": "boolean",
            "confidence": "number",
            "requires_confirmation": "boolean",
            "coverage_notes": ["string"],
            "unmapped_fragment_ids": ["string"],
            "ambiguous_fragment_ids": ["string"],
            "fragment_analyses": [
                {
                    "fragment_id": "string",
                    "artifact_type": "string",
                    "confidence": "number",
                    "title_hint": "string|null",
                    "language": "string|null",
                    "register_signals": ["string"],
                    "needs_review": "boolean",
                    "notes": ["string"],
                }
            ],
        },
        catalogs={
            "artifact_type": BOOTSTRAP_ARTIFACT_TYPE_CATALOG,
        },
    )
def _inventory_stub(config: VaultInitializationConfig, document: SourceDocumentRecord):
    from textifai.bootstrap.contracts import SourceDocumentInventory

    return SourceDocumentInventory(
        source_root=config.vault_root,
        documents=[document],
        total_documents=1,
        total_bytes=document.size_bytes,
        detected_working_languages=[language for language in document.detected_languages if language != "unknown"],
        has_multilingual_material=document.has_mixed_language,
        warnings=[],
    )
