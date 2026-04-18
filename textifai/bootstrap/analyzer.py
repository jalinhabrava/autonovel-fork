from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap.contracts import BOOTSTRAP_ARTIFACT_TYPE_CATALOG, SourceDocumentRecord, SourceFragment
from textifai.bootstrap.prompt_builder import BootstrapPrompt, build_bootstrap_prompt


@dataclass(frozen=True)
class BootstrapFragmentAnalysis:
    fragment_id: str
    artifact_type: str
    confidence: float = 0.0
    title_hint: str | None = None
    language: str | None = None
    detected_languages: list[str] = field(default_factory=list)
    register_signals: list[str] = field(default_factory=list)
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BootstrapDocumentAnalysis:
    source_id: str
    dominant_language: str | None
    detected_languages: list[str] = field(default_factory=list)
    has_mixed_language: bool = False
    fragment_analyses: list[BootstrapFragmentAnalysis] = field(default_factory=list)
    coverage_notes: list[str] = field(default_factory=list)
    unmapped_fragment_ids: list[str] = field(default_factory=list)
    ambiguous_fragment_ids: list[str] = field(default_factory=list)
    requires_confirmation: bool = True
    confidence: float = 0.0
    raw_payload: dict[str, Any] = field(default_factory=dict)


class BootstrapLLMAnalyzer(Protocol):
    def analyze_document(
        self,
        *,
        config,
        document: SourceDocumentRecord,
        text: str,
        fragments: list[SourceFragment],
    ) -> BootstrapDocumentAnalysis | None: ...


@dataclass(frozen=True)
class BootstrapLLMConfig:
    task_name: str = "bootstrap_normalization"
    provider_name: str | None = None
    model: str | None = None
    max_tokens: int = 1800
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 1


class ProviderBackedBootstrapAnalyzer:
    def __init__(self, *, config: BootstrapLLMConfig | None = None) -> None:
        self.config = config or BootstrapLLMConfig()

    def analyze_document(
        self,
        *,
        config,
        document: SourceDocumentRecord,
        text: str,
        fragments: list[SourceFragment],
    ) -> BootstrapDocumentAnalysis | None:
        if get_text_provider_config_error(self.config.task_name, self.config.provider_name):
            return None
        prompt = build_bootstrap_prompt(config=config, document=document, text=text, fragments=fragments)
        payload = json.dumps(
            {
                "prompt_version": prompt.prompt_version,
                "user_payload": prompt.user_payload,
                "required_output_schema": prompt.required_output_schema,
                "catalogs": prompt.catalogs,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        provider = get_text_provider(self.config.task_name, self.config.provider_name)
        response = provider.generate(
            TextGenerationRequest(
                task=self.config.task_name,
                provider_name=self.config.provider_name,
                model=self.config.model,
                system=prompt.system_prompt,
                messages=[TextMessage(role="user", content=payload)],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout_seconds=self.config.timeout_seconds,
                retries=self.config.retries,
            )
        )
        raw_payload = extract_json_payload(response.text)
        if raw_payload is None:
            return None
        return _normalize_analysis_payload(document=document, payload=raw_payload)


def _normalize_analysis_payload(*, document: SourceDocumentRecord, payload: dict[str, Any]) -> BootstrapDocumentAnalysis | None:
    if not isinstance(payload, dict):
        return None
    fragment_analyses: list[BootstrapFragmentAnalysis] = []
    for item in payload.get("fragment_analyses", []):
        raw = item if isinstance(item, dict) else None
        if raw is None:
            continue
        fragment_id = str(raw.get("fragment_id") or "").strip()
        artifact_type = str(raw.get("artifact_type") or "mixed_note").strip()
        if artifact_type not in BOOTSTRAP_ARTIFACT_TYPE_CATALOG:
            artifact_type = "mixed_note"
        if not fragment_id:
            continue
        fragment_analyses.append(
            BootstrapFragmentAnalysis(
                fragment_id=fragment_id,
                artifact_type=artifact_type,
                confidence=_coerce_confidence(raw.get("confidence")),
                title_hint=_clean_text(raw.get("title_hint")),
                language=_clean_text(raw.get("language")),
                detected_languages=_normalize_string_list(raw.get("detected_languages")),
                register_signals=_normalize_string_list(raw.get("register_signals")),
                needs_review=bool(raw.get("needs_review", False)),
                notes=_normalize_string_list(raw.get("notes")),
            )
        )
    detected_languages = _normalize_string_list(payload.get("detected_languages"))
    dominant_language = _clean_text(payload.get("dominant_language"))
    if dominant_language == "mixed":
        dominant_language = None
    return BootstrapDocumentAnalysis(
        source_id=document.source_id,
        dominant_language=dominant_language,
        detected_languages=detected_languages,
        has_mixed_language=bool(payload.get("has_mixed_language", False)),
        fragment_analyses=fragment_analyses,
        coverage_notes=_normalize_string_list(payload.get("coverage_notes")),
        unmapped_fragment_ids=_normalize_string_list(payload.get("unmapped_fragment_ids")),
        ambiguous_fragment_ids=_normalize_string_list(payload.get("ambiguous_fragment_ids")),
        requires_confirmation=bool(payload.get("requires_confirmation", True)),
        confidence=_coerce_confidence(payload.get("confidence")),
        raw_payload=dict(payload),
    )


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))
