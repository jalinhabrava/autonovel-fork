from __future__ import annotations

import re
from dataclasses import dataclass, field

from textifai.bootstrap.contracts import SourceDocumentRecord, SourceFragment
from vault.schema import slugify


_MARKDOWN_DECORATION_RE = re.compile(r"[*_`]+")
_SPANISH_GENERIC_HEADINGS = {
    "no nacen como animales",
    "génesis correcta",
    "genesis correcta",
    "rasgos generales",
    "notas",
    "frases clave",
    "objetivo central",
    "motivaciones internas",
    "rol narrativo",
    "función narrativa",
    "funcion narrativa",
    "personalidad",
    "relaciones",
    "relación con el grupo",
    "relacion con el grupo",
    "hitos narrativos propios",
    "estado actual",
    "importante",
    "esta",
    "qué ocurre",
    "que ocurre",
    "edad aproximada",
    "voz y forma de hablar",
    "apariencia general",
}
_TOPIC_STOPWORDS = {
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "un",
    "una",
    "y",
    "o",
    "en",
    "con",
    "para",
    "que",
    "como",
    "qué",
    "son",
    "sus",
    "por",
}
_WORLD_ENTITY_HINTS = {"nushi", "mana", "bioma", "flujo", "sistema", "mundo", "espíritu", "espiritu"}
_CHARACTER_PROFILE_HINTS = {"edad", "cabello", "ojos", "voz", "motivación", "motivacion", "relación", "relacion"}


@dataclass(frozen=True)
class SemanticBootstrapDraft:
    artifact_type: str
    title: str
    slug: str
    artifact_stage: str
    promotion_status: str
    canonical_subject: str | None = None
    semantic_class: str | None = None
    source_section_title: str | None = None
    fragment_role: str | None = None
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    world_terms: list[str] = field(default_factory=list)
    character_refs: list[str] = field(default_factory=list)
    lore_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def enrich_fragment_semantics(
    *,
    document: SourceDocumentRecord,
    fragment: SourceFragment,
    artifact_type: str,
    fragment_title_hint: str | None,
    fragment_notes: list[str] | None = None,
) -> SemanticBootstrapDraft:
    source_section_title = _clean_heading(fragment_title_hint or _first_heading(fragment.text))
    canonical_subject = _detect_canonical_subject(
        text=fragment.text,
        source_section_title=source_section_title,
        document=document,
    )
    semantic_class = _infer_semantic_class(
        artifact_type=artifact_type,
        text=fragment.text,
        canonical_subject=canonical_subject,
    )
    resolved_artifact_type = _resolve_artifact_type(
        original_artifact_type=artifact_type,
        text=fragment.text,
        semantic_class=semantic_class,
        canonical_subject=canonical_subject,
    )
    topics = _extract_topics(fragment.text, source_section_title=source_section_title)
    world_terms = _extract_world_terms(fragment.text, canonical_subject=canonical_subject)
    character_refs = [canonical_subject] if resolved_artifact_type == "character" and canonical_subject else []
    lore_refs = [canonical_subject] if resolved_artifact_type == "lore" and canonical_subject else []
    entities = _dedupe([*(character_refs or []), *(world_terms or [])])
    fragment_role = _infer_fragment_role(
        source_section_title=source_section_title,
        text=fragment.text,
        semantic_class=semantic_class,
    )
    title = _build_semantic_title(
        resolved_artifact_type=resolved_artifact_type,
        canonical_subject=canonical_subject,
        source_section_title=source_section_title,
        text=fragment.text,
        semantic_class=semantic_class,
    )
    promotion_status = _promotion_status_for(
        artifact_type=resolved_artifact_type,
        canonical_subject=canonical_subject,
        title=title,
        text=fragment.text,
        source_section_title=source_section_title,
    )
    notes = list(fragment_notes or [])
    if resolved_artifact_type != artifact_type:
        notes.append(f"artifact_type_adjusted:{artifact_type}->{resolved_artifact_type}")
    if canonical_subject and canonical_subject != (source_section_title or ""):
        notes.append(f"canonical_subject:{canonical_subject}")
    return SemanticBootstrapDraft(
        artifact_type=resolved_artifact_type,
        title=title,
        slug=_semantic_slug(
            artifact_type=resolved_artifact_type,
            canonical_subject=canonical_subject,
            title=title,
        ),
        artifact_stage="candidate_artifact",
        promotion_status=promotion_status,
        canonical_subject=canonical_subject,
        semantic_class=semantic_class,
        source_section_title=source_section_title,
        fragment_role=fragment_role,
        entities=entities,
        topics=topics,
        world_terms=world_terms,
        character_refs=character_refs,
        lore_refs=lore_refs,
        notes=_dedupe(notes),
    )


def _clean_heading(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lstrip("#").strip()
    text = _MARKDOWN_DECORATION_RE.sub("", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def _generic_heading_key(value: str | None) -> str:
    cleaned = _clean_heading(value) or ""
    cleaned = cleaned.casefold()
    cleaned = re.sub(r"^[^a-záéíóúñ]+", "", cleaned)
    cleaned = re.sub(r"^[0-9.\-–—\s]+", "", cleaned)
    cleaned = cleaned.strip(" :.-–—")
    return cleaned


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped
    return None


def _detect_canonical_subject(
    *,
    text: str,
    source_section_title: str | None,
    document: SourceDocumentRecord,
) -> str | None:
    section = (source_section_title or "").strip()
    section_subject = _subject_from_section_title(section)
    if section_subject:
        return section_subject
    if section and _looks_like_subject(section):
        return section

    patterns = [
        r"\b(?:Un|Una|El|La|Los|Las)\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+)\b",
        r"\b([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+)\s*(?:\:|—|-)\b",
        r"\bLos\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            subject = match.group(1).strip()
            if _looks_like_subject(subject):
                return subject

    candidates = re.findall(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?)\b", text)
    filtered = [item for item in candidates if item.casefold() not in {"Imported Material".casefold(), "Observed Register Signals".casefold()}]
    if filtered:
        ranked = sorted(filtered, key=lambda item: (-text.count(item), len(item)))
        return ranked[0].strip()

    likely = document.likely_content_kinds[0] if document.likely_content_kinds else None
    if likely == "character":
        stem = document.filename.rsplit(".", 1)[0].replace("_", " ").strip()
        if stem:
            return stem
    return None


def _subject_from_section_title(section: str | None) -> str | None:
    cleaned = _clean_heading(section)
    if not cleaned:
        return None
    match = re.search(r"\bde\s+l(?:os|as)\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+)\b", cleaned)
    if match:
        return match.group(1)
    match = re.search(r"\bde\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+)\b", cleaned)
    if match:
        return match.group(1)
    return None


def _looks_like_subject(value: str) -> bool:
    cleaned = _clean_heading(value)
    if not cleaned:
        return False
    lowered = _generic_heading_key(cleaned)
    if lowered in _SPANISH_GENERIC_HEADINGS:
        return False
    words = cleaned.split()
    if len(words) > 6:
        return False
    capitalized = sum(1 for word in words if word[:1].isupper())
    if capitalized >= 1:
        return True
    return lowered in _WORLD_ENTITY_HINTS


def _infer_semantic_class(*, artifact_type: str, text: str, canonical_subject: str | None) -> str | None:
    haystack = f"{canonical_subject or ''} {text[:700]}".casefold()
    if artifact_type == "character":
        if any(hint in haystack for hint in _WORLD_ENTITY_HINTS):
            return "world_entity"
        if any(hint in haystack for hint in _CHARACTER_PROFILE_HINTS):
            return "character_profile"
        return "character_profile"
    if artifact_type == "lore":
        if "nushi" in haystack or "criatura" in haystack or "entidad" in haystack:
            return "world_entity"
        if "mana" in haystack or "ritual" in haystack or "hechizo" in haystack or "magia" in haystack:
            return "magic_concept"
        if "orden" in haystack or "institución" in haystack or "institucion" in haystack:
            return "institution"
        return "lore_concept"
    if artifact_type == "scene":
        return "scene_fragment"
    if artifact_type == "chapter":
        return "chapter_material"
    return "mixed_material"


def _resolve_artifact_type(
    *,
    original_artifact_type: str,
    text: str,
    semantic_class: str | None,
    canonical_subject: str | None,
) -> str:
    haystack = f"{canonical_subject or ''} {text[:900]}".casefold()
    if original_artifact_type == "character" and semantic_class == "world_entity":
        return "lore"
    if original_artifact_type == "project_note":
        if canonical_subject and any(hint in haystack for hint in _WORLD_ENTITY_HINTS):
            return "lore"
    return original_artifact_type


def _extract_topics(text: str, *, source_section_title: str | None) -> list[str]:
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}", f"{source_section_title or ''} {text[:400]}")
    values: list[str] = []
    for token in tokens:
        lowered = token.casefold()
        if lowered in _TOPIC_STOPWORDS:
            continue
        values.append(lowered)
    return _dedupe(values)[:6]


def _extract_world_terms(text: str, *, canonical_subject: str | None) -> list[str]:
    terms = re.findall(r"\b([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+)\b", text[:700])
    values = [term for term in terms if term.casefold() not in {"Imported".casefold(), "Material".casefold()}]
    if canonical_subject:
        values.insert(0, canonical_subject)
    return _dedupe(values)[:6]


def _infer_fragment_role(*, source_section_title: str | None, text: str, semantic_class: str | None) -> str:
    if source_section_title and _clean_heading(source_section_title).casefold() in _SPANISH_GENERIC_HEADINGS:
        return "supporting_subsection"
    if text.strip().startswith("#"):
        return "section_fragment"
    if semantic_class in {"world_entity", "magic_concept", "institution"}:
        return "concept_fragment"
    return "supporting_fragment"


def _build_semantic_title(
    *,
    resolved_artifact_type: str,
    canonical_subject: str | None,
    source_section_title: str | None,
    text: str,
    semantic_class: str | None,
) -> str:
    if canonical_subject:
        qualifier = _qualifier_from_text(text, source_section_title=source_section_title, semantic_class=semantic_class)
        if qualifier and qualifier.casefold() == canonical_subject.casefold():
            qualifier = None
        if qualifier:
            return f"{canonical_subject} - {qualifier}"
        return canonical_subject
    if source_section_title:
        return source_section_title
    first_line = next((line.strip().lstrip("#").strip() for line in text.splitlines() if line.strip()), "Imported Material")
    return first_line or f"{resolved_artifact_type.title()} importado"


def _qualifier_from_text(text: str, *, source_section_title: str | None, semantic_class: str | None) -> str | None:
    haystack = f"{source_section_title or ''} {text[:700]}".casefold()
    if semantic_class == "world_entity":
        if any(term in haystack for term in {"no se reproduce", "no nacen", "creado artificialmente", "invocado"}):
            return "origen y restricciones"
        if any(term in haystack for term in {"fase", "ciclo", "existencia"}):
            return "ciclo de existencia"
        if any(term in haystack for term in {"función natural", "custodia", "protección"}):
            return "función y vínculo"
    if semantic_class == "magic_concept":
        if any(term in haystack for term in {"coste", "costo", "riesgo"}):
            return "costes y riesgos"
        return "marco conceptual"
    cleaned = _generic_heading_key(source_section_title)
    if cleaned and cleaned not in _SPANISH_GENERIC_HEADINGS and len(cleaned.split()) <= 5:
        human = _clean_heading(source_section_title)
        if human:
            short = re.sub(r"\s+de\s+l(?:os|as)\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+\b", "", human).strip(" -:")
            short = re.sub(r"\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+\b", "", short).strip(" -:")
            return short or human
    return None


def _promotion_status_for(
    *,
    artifact_type: str,
    canonical_subject: str | None,
    title: str,
    text: str,
    source_section_title: str | None,
) -> str:
    if artifact_type not in {"character", "lore", "scene", "chapter"}:
        return "staged_candidate"
    if not canonical_subject:
        return "staged_candidate"
    if _generic_heading_key(canonical_subject) in _SPANISH_GENERIC_HEADINGS:
        return "staged_candidate"
    normalized_title = _clean_heading(title)
    if normalized_title and _generic_heading_key(normalized_title) in _SPANISH_GENERIC_HEADINGS:
        return "staged_candidate"
    cleaned_section = _clean_heading(source_section_title)
    if cleaned_section and _generic_heading_key(cleaned_section) in _SPANISH_GENERIC_HEADINGS:
        return "staged_candidate"
    minimum_words = 12 if artifact_type == "lore" else 3
    if len(text.split()) < minimum_words:
        return "staged_candidate"
    if source_section_title and _clean_heading(source_section_title).casefold() in _SPANISH_GENERIC_HEADINGS and " - " not in title:
        return "staged_candidate"
    return "eligible_for_promotion"


def _semantic_slug(*, artifact_type: str, canonical_subject: str | None, title: str) -> str:
    base = canonical_subject or title or artifact_type
    return slugify(base)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result
