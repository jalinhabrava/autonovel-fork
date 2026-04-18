from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from textifai.bootstrap.contracts import LanguageProfile, SourceDocumentInventory, SourceFragment


_JA_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ']+")
_EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "for",
    "from",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "there",
    "this",
    "to",
    "was",
    "were",
    "with",
    "you",
}
_ES_STOPWORDS = {
    "a",
    "al",
    "como",
    "con",
    "de",
    "del",
    "el",
    "ella",
    "ellos",
    "en",
    "es",
    "esta",
    "este",
    "la",
    "las",
    "lo",
    "los",
    "más",
    "no",
    "o",
    "para",
    "pero",
    "por",
    "que",
    "se",
    "su",
    "sus",
    "un",
    "una",
    "y",
}
_KNOWN_LANGUAGE_CODES = {"en", "es", "ja"}


@dataclass(frozen=True)
class DetectedLanguageProfile:
    dominant_language: str | None
    detected_languages: list[str]
    has_mixed_language: bool
    register_signals: list[str]


def detect_language_profile(text: str) -> DetectedLanguageProfile:
    tokens = [token.casefold() for token in _WORD_RE.findall(text)]
    token_count = len(tokens) or 1
    scores = Counter[str]()
    scores["en"] = sum(1 for token in tokens if token in _EN_STOPWORDS)
    scores["es"] = sum(1 for token in tokens if token in _ES_STOPWORDS)
    scores["ja"] = 0
    if _JA_RE.search(text):
        scores["ja"] = max(1, len(_JA_RE.findall(text)) // 8)

    language_scores = _normalize_scores(scores, token_count)
    detected_languages = [language for language, score in language_scores if score > 0.02]
    dominant_language = detected_languages[0] if detected_languages else None
    has_mixed_language = len(detected_languages) > 1
    if has_mixed_language and dominant_language is not None:
        dominant_language = "mixed"
    register_signals = _infer_register_signals(text)
    return DetectedLanguageProfile(
        dominant_language=dominant_language,
        detected_languages=detected_languages,
        has_mixed_language=has_mixed_language,
        register_signals=register_signals,
    )


def build_language_profile(
    inventory: SourceDocumentInventory,
    fragments_by_source: dict[str, list[SourceFragment]],
    source_texts: dict[str, str],
    *,
    project_primary_language: str | None = None,
    working_languages: Iterable[str] = (),
) -> LanguageProfile:
    document_languages: dict[str, list[str]] = {}
    fragment_languages: dict[str, str] = {}
    register_signals_by_language: dict[str, list[str]] = {}
    detected_counts: Counter[str] = Counter()
    has_multilingual_documents = False

    for document in inventory.documents:
        text = source_texts.get(document.source_id, "")
        detected = detect_language_profile(text)
        document_languages[document.source_id] = list(detected.detected_languages)
        if detected.dominant_language is not None:
            detected_counts[detected.dominant_language] += 1
        if detected.has_mixed_language:
            has_multilingual_documents = True
        for fragment in fragments_by_source.get(document.source_id, []):
            fragment_languages[fragment.fragment_id] = fragment.language or detected.dominant_language or "unknown"
            for language in _fragment_languages(fragment, detected):
                register_signals_by_language.setdefault(language, [])
                register_signals_by_language[language] = _dedupe(
                    register_signals_by_language[language] + list(fragment.register_signals)
                )

    observed_languages = _dedupe(
        [language for language in [project_primary_language, *working_languages] if language]
        + [language for language in detected_counts if language in _KNOWN_LANGUAGE_CODES]
    )
    resolved_primary = project_primary_language
    if resolved_primary is None and detected_counts:
        resolved_primary = detected_counts.most_common(1)[0][0]
    if resolved_primary == "mixed":
        resolved_primary = None
    if len([language for language in detected_counts if language not in {"unknown", "mixed"}]) > 1:
        has_multilingual_documents = True

    return LanguageProfile(
        project_primary_language=resolved_primary,
        working_languages=observed_languages,
        document_languages=document_languages,
        fragment_languages=fragment_languages,
        has_multilingual_documents=has_multilingual_documents,
        register_signals_by_language=register_signals_by_language,
    )


def _normalize_scores(scores: Counter[str], token_count: int) -> list[tuple[str, float]]:
    ordered = []
    for language, score in scores.items():
        if score <= 0:
            continue
        ordered.append((language, score / token_count))
    ordered.sort(key=lambda item: item[1], reverse=True)
    return ordered


def _infer_register_signals(text: str) -> list[str]:
    signals: list[str] = []
    stripped = text.strip()
    if not stripped:
        return ["empty"]
    if stripped.startswith("#"):
        signals.append("markdown_heading")
    if any(line.lstrip().startswith(("-", "*")) for line in stripped.splitlines()):
        signals.append("bullet_list")
    if "—" in stripped or stripped.count('"') >= 2 or stripped.count("“") >= 2 or stripped.count("¿") >= 1:
        signals.append("dialogue_or_conversational")
    if len(stripped.splitlines()) > 1:
        signals.append("multi_line_prose")
    if not signals:
        signals.append("freeform_prose")
    return signals


def _fragment_languages(fragment: SourceFragment, detected: DetectedLanguageProfile) -> list[str]:
    if fragment.language and fragment.language != "unknown":
        return [fragment.language]
    if detected.dominant_language is not None:
        return [detected.dominant_language]
    return ["unknown"]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
