from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textifai.derived_sources.contracts import DerivedExtractionSeed, LLMEscalationDecision


@dataclass(frozen=True)
class DerivedSourcePrompt:
    prompt_version: str
    system_prompt: str
    user_payload: dict[str, Any]
    required_output_schema: dict[str, Any]
    catalogs: dict[str, tuple[str, ...]]


def build_derived_understanding_prompt(
    *,
    seed: DerivedExtractionSeed,
    escalation: LLMEscalationDecision,
) -> DerivedSourcePrompt:
    return DerivedSourcePrompt(
        prompt_version="1",
        system_prompt=(
            "You analyze derived source documents for TextifAI. "
            "Treat the input as potentially degraded or multilingual. "
            "Do not rewrite, summarize, translate, or invent missing content. "
            "Return only JSON and explicitly mark uncertainty."
        ),
        user_payload={
            "source_id": seed.source_id,
            "source_format": seed.source_format,
            "source_path": seed.source_path,
            "document_metadata": seed.metadata,
            "quality_signals": seed.quality_signals,
            "warnings": seed.warnings,
            "detected_languages": seed.detected_languages,
            "dominant_language": seed.dominant_language,
            "has_mixed_language": seed.has_mixed_language,
            "raw_extracted_text": seed.raw_extracted_text[:12000],
            "lightweight_blocks": [
                {
                    "block_id": block.block_id,
                    "text": block.text[:2400],
                    "heading_text": block.heading_text,
                    "probable_kind": block.probable_kind,
                    "language": block.language,
                    "mixed_content": block.mixed_content,
                    "confidence": block.confidence,
                    "boundary_hints": block.boundary_hints,
                    "notes": block.notes,
                }
                for block in seed.lightweight_blocks
            ],
            "llm_escalation": {
                "required": escalation.required,
                "reasons": escalation.reasons,
            },
            "analysis_targets": [
                "recover_usable_text_if_possible",
                "detect_block_boundaries",
                "recover_probable_headings",
                "recover_probable_order",
                "detect_content_mix",
                "detect_language_mix",
                "flag_structural_loss",
                "propose_segment_candidates",
                "return_structured_json_only",
            ],
        },
        required_output_schema={
            "source_id": "string",
            "dominant_language": "string|null",
            "detected_languages": ["string"],
            "has_mixed_language": "boolean",
            "overall_confidence": "number",
            "structural_confidence": "number",
            "content_mix_signals": ["string"],
            "warnings": ["string"],
            "segment_candidates": [
                {
                    "candidate_id": "string",
                    "segment_text": "string",
                    "heading_text": "string|null",
                    "probable_kind": "string",
                    "language": "string|null",
                    "confidence": "number",
                    "mixed_content": "boolean",
                    "boundary_hints": ["string"],
                    "notes": ["string"],
                }
            ],
            "structure_signals": {
                "recovered_headings": ["string"],
                "probable_block_order": ["string"],
                "recovered_lists": ["string"],
                "ordering_confidence": "number",
                "structure_warnings": ["string"],
                "confidence": "number",
            },
            "loss_signals": {
                "missing_structure_signals": ["string"],
                "paragraph_merge_signals": ["string"],
                "heading_loss_signals": ["string"],
                "ordering_uncertainty_signals": ["string"],
                "coverage_risk_notes": ["string"],
                "severity": "string",
                "mixed_language_degradation": ["string"],
            },
            "needs_manual_review": "boolean",
            "recognized_or_recovered_text": "string",
        },
        catalogs={
            "source_format": ("txt", "md", "docx", "pdf", "doc"),
        },
    )
