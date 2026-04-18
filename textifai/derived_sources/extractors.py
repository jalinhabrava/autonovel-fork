from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from textifai.bootstrap.language import detect_language_profile
from textifai.derived_sources.contracts import (
    DERIVED_SOURCE_FORMAT_CATALOG,
    DerivedExtractionSeed,
    FormatExtractionProfile,
    LightExtractionBlock,
)


TEXT_FORMATS = {"md", "txt"}
DERIVED_FORMATS = {"docx", "pdf", "doc"}


@dataclass(frozen=True)
class ExtractionQuality:
    quality_signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    llm_escalation_reasons: list[str] = field(default_factory=list)


def detect_source_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lstrip(".").casefold()
    if suffix in DERIVED_SOURCE_FORMAT_CATALOG:
        return suffix
    return suffix or "txt"


def extract_light_source(path: str | Path) -> DerivedExtractionSeed:
    source_path = Path(path).expanduser().resolve()
    source_format = detect_source_format(source_path)
    raw_bytes = source_path.read_bytes() if source_path.exists() else b""
    checksum = hashlib.sha256(raw_bytes).hexdigest()

    if source_format in TEXT_FORMATS:
        text = _decode_text(raw_bytes)
        blocks = _build_blocks(text)
        detection = detect_language_profile(text)
        profile = FormatExtractionProfile(
            source_format=source_format,
            extraction_method="native_text",
            is_native_text=True,
            text_fidelity_confidence=0.98 if text.strip() else 0.7,
            structural_fidelity_confidence=0.95 if len(blocks) > 1 else 0.85,
            loss_risk_flags=[],
            warnings=[],
            llm_escalation_required=False,
            llm_escalation_reasons=[],
        )
        return DerivedExtractionSeed(
            source_id=_source_id(source_path, checksum),
            source_path=str(source_path),
            source_format=source_format,
            raw_extracted_text=text,
            lightweight_blocks=blocks,
            detected_languages=list(detection.detected_languages),
            dominant_language=detection.dominant_language,
            has_mixed_language=detection.has_mixed_language,
            quality_signals=["native_text"],
            warnings=[],
            format_profile=profile,
            checksum=checksum,
            size_bytes=len(raw_bytes),
            metadata={"source_type": "native_text"},
        )

    extracted_text, method_notes = _extract_derived_text(source_path, source_format, raw_bytes)
    blocks = _build_blocks(extracted_text)
    detection = detect_language_profile(extracted_text)
    quality = _collect_quality_signals(
        source_format=source_format,
        extracted_text=extracted_text,
        blocks=blocks,
        raw_bytes=raw_bytes,
        detected_languages=list(detection.detected_languages),
        has_mixed_language=detection.has_mixed_language,
    )
    llm_required, llm_reasons = _should_escalate_to_llm(
        source_format=source_format,
        extracted_text=extracted_text,
        quality=quality,
        blocks=blocks,
        has_mixed_language=detection.has_mixed_language,
    )
    profile = FormatExtractionProfile(
        source_format=source_format,
        extraction_method="light_extraction" if extracted_text.strip() else "llm_first_derived",
        is_native_text=False,
        text_fidelity_confidence=_text_confidence(source_format, extracted_text, raw_bytes),
        structural_fidelity_confidence=_structure_confidence(source_format, blocks, quality.quality_signals),
        loss_risk_flags=_dedupe([*quality.quality_signals, *method_notes]),
        warnings=list(quality.warnings),
        llm_escalation_required=llm_required,
        llm_escalation_reasons=llm_reasons,
    )
    return DerivedExtractionSeed(
        source_id=_source_id(source_path, checksum),
        source_path=str(source_path),
        source_format=source_format,
        raw_extracted_text=extracted_text,
        lightweight_blocks=blocks,
        detected_languages=list(detection.detected_languages),
        dominant_language=detection.dominant_language,
        has_mixed_language=detection.has_mixed_language,
        quality_signals=quality.quality_signals,
        warnings=quality.warnings,
        format_profile=profile,
        checksum=checksum,
        size_bytes=len(raw_bytes),
        metadata={"source_type": "derived", "method_notes": method_notes},
    )


def _extract_derived_text(path: Path, source_format: str, raw_bytes: bytes) -> tuple[str, list[str]]:
    if source_format == "docx":
        text, notes = _extract_docx_text(path, raw_bytes)
        if text.strip():
            return text, notes
        return "", [*notes, "docx_text_unavailable"]
    if source_format == "pdf":
        text, notes = _extract_pdf_text(path, raw_bytes)
        if text.strip():
            return text, notes
        return "", [*notes, "pdf_text_unavailable"]
    if source_format == "doc":
        text = _extract_doc_text(raw_bytes)
        if text.strip():
            return text, ["doc_heuristic_extraction"]
        return _decode_text(raw_bytes), ["doc_fallback_bytes"]
    return _decode_text(raw_bytes), ["unknown_format_fallback"]


def _extract_docx_text(path: Path, raw_bytes: bytes) -> tuple[str, list[str]]:
    notes: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            document_xml = zf.read("word/document.xml")
            tree = ET.fromstring(document_xml)
            namespace = {
                "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            }
            paragraphs: list[str] = []
            for paragraph in tree.findall(".//w:p", namespace):
                runs = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
                text = " ".join(run.strip() for run in runs if run.strip()).strip()
                if text:
                    paragraphs.append(text)
            if paragraphs:
                return "\n\n".join(paragraphs), ["docx_xml"]
            notes.append("docx_no_paragraphs")
    except (KeyError, FileNotFoundError, zipfile.BadZipFile, ET.ParseError):
        notes.append("docx_parse_failed")
    return "", notes


def _extract_pdf_text(path: Path, raw_bytes: bytes) -> tuple[str, list[str]]:
    notes: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        PdfReader = None
    if PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(page.strip() for page in pages if page.strip())
            if text.strip():
                return text, ["pdf_parser:pypdf"]
            notes.append("pdf_no_extractable_text")
        except Exception:
            notes.append("pdf_parser_failed")
    literal_text = _extract_pdf_literals(raw_bytes)
    if literal_text.strip():
        return literal_text, [*notes, "pdf_literal_text"]
    return "", [*notes, "pdf_text_unavailable"]


def _extract_doc_text(raw_bytes: bytes) -> str:
    text = _decode_text(raw_bytes)
    if not text.strip():
        return ""
    printable = [line.strip() for line in text.splitlines() if len(line.strip()) > 1]
    return "\n\n".join(printable)


def _build_blocks(text: str) -> list[LightExtractionBlock]:
    blocks: list[LightExtractionBlock] = []
    for index, block_text in enumerate(_split_blocks(text), start=1):
        detection = detect_language_profile(block_text)
        blocks.append(
            LightExtractionBlock(
                block_id=f"block_{index:03d}",
                text=block_text,
                heading_text=_heading_hint(block_text),
                probable_kind=_probable_kind(block_text),
                language=detection.dominant_language,
                mixed_content=detection.has_mixed_language,
                confidence=0.9 if block_text.strip() else 0.0,
                boundary_hints=["blank_line_boundary"] if len(text.splitlines()) > 1 else ["single_block"],
                notes=list(detection.register_signals),
            )
        )
    if not blocks:
        blocks.append(
            LightExtractionBlock(
                block_id="block_001",
                text=text,
                heading_text=None,
                probable_kind="uncertain",
                language=None,
                mixed_content=False,
                confidence=0.0,
                boundary_hints=["empty_or_single_block"],
                notes=["empty"],
            )
        )
    return blocks


def _split_blocks(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    parts = [part.strip() for part in re.split(r"\n\s*\n", stripped) if part.strip()]
    return parts if parts else [stripped]


def _heading_hint(text: str) -> str | None:
    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
    if first_line.startswith("#"):
        return first_line.lstrip("#").strip() or None
    return None


def _probable_kind(text: str) -> str:
    haystack = text.casefold()
    if any(term in haystack for term in {"chapter", "capítulo", "capitulo"}):
        return "chapter"
    if any(term in haystack for term in {"scene", "escena"}):
        return "scene"
    if any(term in haystack for term in {"character", "personaje", "profile", "bio"}):
        return "character"
    if any(term in haystack for term in {"lore", "world", "worldbuilding", "mundo", "canon"}):
        return "lore"
    if len(text.split()) > 220:
        return "mixed_note"
    return "uncertain"


def _collect_quality_signals(
    *,
    source_format: str,
    extracted_text: str,
    blocks: list[LightExtractionBlock],
    raw_bytes: bytes,
    detected_languages: list[str],
    has_mixed_language: bool,
) -> ExtractionQuality:
    signals: list[str] = []
    warnings: list[str] = []
    llm_reasons: list[str] = []
    if not extracted_text.strip():
        signals.append("non_extractable_text")
        warnings.append("no_text_extracted")
        llm_reasons.append("non_extractable_text")
    if len(extracted_text.strip()) < 40 and source_format in DERIVED_FORMATS:
        signals.append("extraction_too_sparse")
        llm_reasons.append("extraction_too_sparse")
    if len(blocks) <= 1 and len(extracted_text.splitlines()) > 6:
        signals.append("paragraph_merge_risk")
        llm_reasons.append("paragraph_merge_risk")
    if not any(block.heading_text for block in blocks):
        if source_format in {"pdf", "doc"}:
            signals.append("heading_loss_risk")
            llm_reasons.append("heading_loss_risk")
        elif source_format == "docx" and len(extracted_text.split()) > 250 and len(blocks) <= 1:
            signals.append("heading_loss_risk")
            llm_reasons.append("heading_loss_risk")
    if len(extracted_text.split()) > 0 and len(raw_bytes) > 0:
        text_density = len(extracted_text.split()) / max(1, len(raw_bytes) / 12)
        if text_density < 0.25:
            signals.append("low_text_density")
            llm_reasons.append("low_text_density")
    if has_mixed_language or len([language for language in detected_languages if language not in {"unknown", "mixed"}]) > 1:
        signals.append("mixed_language_detected")
        warnings.append("mixed_language")
        llm_reasons.append("mixed_language_detected")
    if len(blocks) > 1:
        probable_kinds = {block.probable_kind for block in blocks}
        if len(probable_kinds) > 2:
            signals.append("mixed_content_detected")
            llm_reasons.append("mixed_content_detected")
    if source_format == "pdf":
        signals.append("format_visually_complex")
        llm_reasons.append("format_visually_complex")
    return ExtractionQuality(
        quality_signals=_dedupe(signals),
        warnings=_dedupe(warnings),
        llm_escalation_reasons=_dedupe(llm_reasons),
    )


def _should_escalate_to_llm(
    *,
    source_format: str,
    extracted_text: str,
    quality: ExtractionQuality,
    blocks: list[LightExtractionBlock],
    has_mixed_language: bool,
) -> tuple[bool, list[str]]:
    reasons = list(quality.llm_escalation_reasons)
    if source_format in DERIVED_FORMATS:
        if not extracted_text.strip():
            reasons.append("non_extractable_text")
        if len(quality.quality_signals) > 0:
            reasons.extend(quality.quality_signals)
        if has_mixed_language:
            reasons.append("mixed_language_detected")
        if len(blocks) <= 1 and source_format in {"pdf", "doc"}:
            reasons.append("low_structural_quality")
    reasons = _dedupe(reasons)
    return bool(reasons), reasons


def _text_confidence(source_format: str, extracted_text: str, raw_bytes: bytes) -> float:
    if source_format in TEXT_FORMATS:
        return 0.98 if extracted_text.strip() else 0.7
    if not extracted_text.strip():
        return 0.15
    density = len(extracted_text.split()) / max(1, len(raw_bytes) / 8)
    return max(0.2, min(0.85, density))


def _structure_confidence(source_format: str, blocks: list[LightExtractionBlock], signals: list[str]) -> float:
    if source_format in TEXT_FORMATS:
        return 0.95 if len(blocks) > 1 else 0.85
    score = 0.6
    if any(block.heading_text for block in blocks):
        score += 0.15
    if len(blocks) > 1:
        score += 0.1
    if "heading_loss_risk" in signals:
        score -= 0.2
    if "paragraph_merge_risk" in signals:
        score -= 0.15
    return max(0.1, min(0.9, score))


def _extract_pdf_literals(raw_bytes: bytes) -> str:
    decoded = raw_bytes.decode("latin-1", errors="ignore")
    candidates = re.findall(r"\(([^()]*)\)\s*Tj", decoded)
    if not candidates:
        candidates = re.findall(r"\[(.*?)\]\s*TJ", decoded, flags=re.DOTALL)
    text = "\n".join(_clean_pdf_text(candidate) for candidate in candidates if candidate.strip())
    return text.strip()


def _clean_pdf_text(value: str) -> str:
    value = value.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
    return re.sub(r"\\([()\\])", r"\1", value)


def _decode_text(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("utf-8", errors="replace")


def _source_id(path: Path, checksum: str) -> str:
    stem = "".join(ch for ch in path.stem.lower() if ch.isalnum())[:20] or "source"
    return f"{stem}_{checksum[:10]}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
