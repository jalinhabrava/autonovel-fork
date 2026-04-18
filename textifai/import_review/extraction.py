from __future__ import annotations

from pathlib import Path

from interactive.query import parse_frontmatter
from textifai.bootstrap.contracts import ImportProvenance
from textifai.import_review.contracts import EXTRACTION_MODE_CATALOG, ExtractionProfile


DERIVED_FORMATS = {"pdf", "docx", "doc"}
NATIVE_FORMATS = {"md", "txt"}


def extraction_profile_from_metadata(
    *,
    path: str | Path,
    provenance: ImportProvenance | None,
    frontmatter: dict[str, str] | None = None,
) -> ExtractionProfile:
    path = Path(path)
    frontmatter = frontmatter or {}
    source_format = _clean_text(
        frontmatter.get("source_format")
        or frontmatter.get("source_extension")
        or (provenance.source_format if provenance else None)
        or path.suffix.lstrip(".")
        or "md"
    )
    extraction_mode = _clean_text(
        frontmatter.get("extraction_mode")
        or (provenance.extraction_mode if provenance else None)
        or ("native_text" if source_format in NATIVE_FORMATS else "derived_text_extraction")
    )
    if extraction_mode not in EXTRACTION_MODE_CATALOG:
        extraction_mode = "derived_text_extraction" if source_format not in NATIVE_FORMATS else "native_text"
    extraction_confidence = _coerce_float(
        frontmatter.get("extraction_confidence")
        or (provenance.extraction_confidence if provenance else None)
        or (1.0 if source_format in NATIVE_FORMATS else 0.7)
    )
    structural_confidence = _coerce_float(
        frontmatter.get("structural_confidence")
        or (provenance.structural_confidence if provenance else None)
        or (1.0 if source_format in NATIVE_FORMATS else 0.7)
    )
    warnings = _split_values(
        frontmatter.get("warnings")
        or (",".join(provenance.warnings) if provenance and provenance.warnings else "")
    )
    loss_risk_flags = _split_values(
        frontmatter.get("loss_risk_flags")
        or (",".join(provenance.loss_risk_flags) if provenance and provenance.loss_risk_flags else "")
    )
    if source_format in DERIVED_FORMATS and extraction_mode == "native_text":
        extraction_mode = "derived_text_extraction"
    if source_format in NATIVE_FORMATS and extraction_mode == "derived_text_extraction":
        warnings.append("native_text_marked_as_derived")
    return ExtractionProfile(
        source_format=source_format,
        extraction_mode=extraction_mode,
        extraction_confidence=extraction_confidence,
        structural_confidence=structural_confidence,
        warnings=_dedupe(warnings),
        loss_risk_flags=_dedupe(loss_risk_flags),
    )


def extraction_requires_strict_confirmation(profile: ExtractionProfile | None) -> bool:
    if profile is None:
        return True
    if profile.extraction_mode == "native_text":
        return profile.extraction_confidence < 0.8 or profile.structural_confidence < 0.8
    return profile.extraction_confidence < 0.9 or profile.structural_confidence < 0.9 or bool(profile.loss_risk_flags)


def is_native_text(profile: ExtractionProfile | None) -> bool:
    return bool(profile and profile.extraction_mode == "native_text")


def parse_staging_frontmatter(text: str) -> dict[str, str]:
    return parse_frontmatter(text)


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip() or ""


def _coerce_float(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _split_values(raw: str) -> list[str]:
    if not raw:
        return []
    values = [item.strip() for item in str(raw).split(",") if item.strip()]
    return _dedupe(values)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
