from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider, get_text_provider_config_error
from providers.text_provider import TextProviderError
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap.contracts import BOOTSTRAP_ARTIFACT_TYPE_CATALOG, SourceDocumentRecord, SourceFragment
from textifai.bootstrap.prompt_builder import BootstrapPrompt, build_bootstrap_prompt
from textifai.bootstrap.segmenter import segment_source_document


@dataclass(frozen=True)
class BootstrapFragmentAnalysis:
    fragment_id: str
    artifact_type: str
    confidence: float = 0.0
    title_hint: str | None = None
    canonical_subject: str | None = None
    semantic_class: str | None = None
    promotion_status: str | None = None
    fragment_role: str | None = None
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    world_terms: list[str] = field(default_factory=list)
    character_refs: list[str] = field(default_factory=list)
    lore_refs: list[str] = field(default_factory=list)
    language: str | None = None
    detected_languages: list[str] = field(default_factory=list)
    register_signals: list[str] = field(default_factory=list)
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BootstrapDocumentAnalysis:
    source_id: str
    dominant_language: str | None
    source_format: str = "md"
    extraction_mode: str = "native_text"
    extraction_confidence: float = 1.0
    structural_confidence: float = 1.0
    llm_used: bool = False
    recognized_or_recovered_text: str | None = None
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
    max_tokens: int = 4000
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 1
    progress_log_path: str | None = None


class ProviderBackedBootstrapAnalyzer:
    def __init__(self, *, config: BootstrapLLMConfig | None = None) -> None:
        self.config = config or BootstrapLLMConfig()
        self.derived_config = None

    def analyze_document(
        self,
        *,
        config,
        document: SourceDocumentRecord,
        text: str,
        fragments: list[SourceFragment],
    ) -> BootstrapDocumentAnalysis | None:
        if document.extension in {"docx", "pdf", "doc"}:
            return self._analyze_derived_document(document=document, text=text, fragments=fragments)
        if get_text_provider_config_error(self.config.task_name, self.config.provider_name):
            return None
        if _should_batch_document(text=text, fragments=fragments):
            _emit_progress(self.config.progress_log_path, phase="analyze_document", event="batch_mode", source_id=document.source_id, fragment_count=len(fragments))
            return self._analyze_document_in_batches(config=config, document=document, fragments=fragments)
        analysis = self._analyze_fragment_batch(
            config=config,
            document=document,
            text=text,
            fragments=fragments,
        )
        if analysis is not None:
            return analysis
        if len(fragments) > 1:
            _emit_progress(self.config.progress_log_path, phase="analyze_document", event="batch_fallback_after_full_failure", source_id=document.source_id, fragment_count=len(fragments))
            return self._analyze_document_in_batches(config=config, document=document, fragments=fragments)
        return None

    def _analyze_derived_document(
        self,
        *,
        document: SourceDocumentRecord,
        text: str,
        fragments: list[SourceFragment],
    ) -> BootstrapDocumentAnalysis:
        from textifai.derived_sources import (
            DerivedSourceLLMConfig,
            ProviderBackedDerivedSourceInterpreter,
            decide_llm_escalation,
            extract_light_source,
            review_derived_source,
            validate_derived_extraction,
        )

        if self.derived_config is None:
            self.derived_config = DerivedSourceLLMConfig(
                task_name=self.config.task_name,
                provider_name=self.config.provider_name,
                model=self.config.model,
                max_tokens=max(self.config.max_tokens, 1800),
                temperature=self.config.temperature,
                timeout_seconds=self.config.timeout_seconds,
                retries=self.config.retries,
            )
        seed = extract_light_source(document.path)
        escalation = decide_llm_escalation(seed)
        llm_payload = None
        validated_extraction = None
        if not get_text_provider_config_error(self.derived_config.task_name, self.derived_config.provider_name) and escalation.required:
            interpreter = ProviderBackedDerivedSourceInterpreter(config=self.derived_config)
            try:
                llm_payload = interpreter.interpret(seed=seed, escalation=escalation)
                validated_extraction = validate_derived_extraction(seed=seed, payload=llm_payload)
            except TextProviderError as exc:
                _emit_progress(
                    self.config.progress_log_path,
                    phase="analyze_derived_document",
                    event="provider_error",
                    source_id=document.source_id,
                    error=str(exc),
                )
                llm_payload = None
                validated_extraction = validate_derived_extraction(seed=seed, payload=None)
        else:
            validated_extraction = validate_derived_extraction(seed=seed, payload=None)

        review = review_derived_source(
            seed=seed,
            escalation=escalation,
            validated_extraction=validated_extraction,
            llm_payload=llm_payload,
        )
        recognized_text = validated_extraction.recognized_or_recovered_text if validated_extraction else text
        segmented = segment_source_document(document, recognized_text or text or seed.raw_extracted_text)
        fragment_analyses = _derived_fragment_analyses(
            document=document,
            source_fragments=fragments,
            llm_payload=llm_payload,
        )
        coverage_notes = list(dict.fromkeys([*seed.quality_signals, *seed.warnings, *review.notes]))
        unmapped_fragment_ids = [fragment.fragment_id for fragment in segmented if fragment.needs_review]
        ambiguous_fragment_ids = [
            fragment.fragment_id
            for fragment in segmented
            if fragment.needs_review or fragment.kind_confidence < 0.65
        ]
        return BootstrapDocumentAnalysis(
            source_id=document.source_id,
            dominant_language=(validated_extraction.dominant_language if validated_extraction else seed.dominant_language)
            or seed.dominant_language,
            source_format=seed.source_format,
            extraction_mode=(
                "llm_first_derived"
                if llm_payload is not None and not seed.raw_extracted_text.strip()
                else "llm_assisted_derived"
                if llm_payload is not None
                else seed.format_profile.extraction_method
                if seed.format_profile
                else "derived_text_extraction"
            ),
            extraction_confidence=validated_extraction.confidence if validated_extraction else (seed.format_profile.extraction_confidence if seed.format_profile else 0.0),
            structural_confidence=validated_extraction.structural_confidence if validated_extraction else (seed.format_profile.structural_fidelity_confidence if seed.format_profile else 0.0),
            llm_used=llm_payload is not None,
            recognized_or_recovered_text=validated_extraction.recognized_or_recovered_text if validated_extraction else seed.raw_extracted_text,
            detected_languages=validated_extraction.detected_languages if validated_extraction else list(seed.detected_languages),
            has_mixed_language=validated_extraction.has_mixed_language if validated_extraction else seed.has_mixed_language,
            fragment_analyses=fragment_analyses,
            coverage_notes=coverage_notes,
            unmapped_fragment_ids=unmapped_fragment_ids if review.review_status != "usable" else [],
            ambiguous_fragment_ids=ambiguous_fragment_ids,
            requires_confirmation=review.strict_confirmation_required or review.review_status != "usable",
            confidence=review.final_confidence,
            raw_payload={
                "seed": seed.metadata,
                "escalation": {"required": escalation.required, "reasons": escalation.reasons},
                "llm_used": llm_payload is not None,
                "review_status": review.review_status,
            },
        )

    def _analyze_document_in_batches(
        self,
        *,
        config,
        document: SourceDocumentRecord,
        fragments: list[SourceFragment],
    ) -> BootstrapDocumentAnalysis | None:
        analyses: list[BootstrapDocumentAnalysis] = []
        batches = _batched_fragments(fragments)
        for index, batch in enumerate(batches, start=1):
            _emit_progress(self.config.progress_log_path, phase="analyze_batch", event="batch_started", source_id=document.source_id, batch_index=index, batch_total=len(batches), batch_size=len(batch))
            analysis = self._analyze_fragment_batch_recursive(
                config=config,
                document=document,
                fragments=batch,
            )
            if analysis is not None:
                analyses.append(analysis)
                _emit_progress(self.config.progress_log_path, phase="analyze_batch", event="batch_succeeded", source_id=document.source_id, batch_index=index, fragment_analysis_count=len(analysis.fragment_analyses))
            else:
                _emit_progress(self.config.progress_log_path, phase="analyze_batch", event="batch_failed", source_id=document.source_id, batch_index=index)
        if not analyses:
            return None
        return _merge_document_analyses(document=document, analyses=analyses, total_fragments=fragments)

    def _analyze_fragment_batch_recursive(
        self,
        *,
        config,
        document: SourceDocumentRecord,
        fragments: list[SourceFragment],
    ) -> BootstrapDocumentAnalysis | None:
        text = _text_for_fragments(fragments)
        analysis = self._analyze_fragment_batch(
            config=config,
            document=document,
            text=text,
            fragments=fragments,
        )
        if analysis is not None:
            return analysis
        if len(fragments) <= 1:
            _emit_progress(self.config.progress_log_path, phase="analyze_batch", event="single_fragment_failed", source_id=document.source_id, fragment_id=fragments[0].fragment_id if fragments else None)
            return None
        midpoint = max(1, len(fragments) // 2)
        _emit_progress(self.config.progress_log_path, phase="analyze_batch", event="recursive_split", source_id=document.source_id, left_count=midpoint, right_count=len(fragments) - midpoint)
        left = self._analyze_fragment_batch_recursive(
            config=config,
            document=document,
            fragments=fragments[:midpoint],
        )
        right = self._analyze_fragment_batch_recursive(
            config=config,
            document=document,
            fragments=fragments[midpoint:],
        )
        parts = [item for item in (left, right) if item is not None]
        if not parts:
            return None
        return _merge_document_analyses(document=document, analyses=parts, total_fragments=fragments)

    def _analyze_fragment_batch(
        self,
        *,
        config,
        document: SourceDocumentRecord,
        text: str,
        fragments: list[SourceFragment],
    ) -> BootstrapDocumentAnalysis | None:
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
        try:
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
        except TextProviderError as exc:
            _emit_progress(
                self.config.progress_log_path,
                phase="analyze_batch",
                event="provider_error",
                source_id=document.source_id,
                error=str(exc),
            )
            return None
        raw_payload = extract_json_payload(response.text)
        if raw_payload is None:
            return None
        return _normalize_analysis_payload(document=document, payload=raw_payload)


def _derived_fragment_analyses(
    *,
    document: SourceDocumentRecord,
    source_fragments: list[SourceFragment],
    llm_payload,
) -> list[BootstrapFragmentAnalysis]:
    analyses: list[BootstrapFragmentAnalysis] = []
    llm_candidates = list(getattr(llm_payload, "segment_candidates", []) or [])
    for index, fragment in enumerate(source_fragments):
        candidate = llm_candidates[index] if index < len(llm_candidates) else None
        artifact_type = fragment.detected_kind
        confidence = fragment.kind_confidence
        title_hint = fragment.text.strip().splitlines()[0].strip().lstrip("#").strip() if fragment.text.strip() else None
        language = fragment.language or document.dominant_language
        register_signals = list(fragment.register_signals)
        needs_review = fragment.needs_review
        notes: list[str] = []
        if candidate is not None:
            artifact_type = candidate.probable_kind or artifact_type
            confidence = max(confidence, candidate.confidence)
            title_hint = candidate.heading_text or title_hint
            language = candidate.language or language
            register_signals = list(dict.fromkeys([*register_signals, *candidate.boundary_hints, *candidate.notes]))
            needs_review = needs_review or candidate.mixed_content or candidate.confidence < 0.55
            if candidate.notes:
                notes.extend(candidate.notes)
        if artifact_type not in BOOTSTRAP_ARTIFACT_TYPE_CATALOG:
            artifact_type = "mixed_note"
        analyses.append(
            BootstrapFragmentAnalysis(
                fragment_id=fragment.fragment_id,
                artifact_type=artifact_type,
                confidence=confidence,
                title_hint=title_hint,
                canonical_subject=None,
                semantic_class=None,
                promotion_status=None,
                fragment_role=None,
                entities=[],
                topics=[],
                world_terms=[],
                character_refs=[],
                lore_refs=[],
                language=language,
                detected_languages=[language] if language else [],
                register_signals=list(dict.fromkeys(register_signals)),
                needs_review=needs_review,
                notes=list(dict.fromkeys(notes)),
            )
        )
    if len(llm_candidates) > len(source_fragments):
        analyses.append(
            BootstrapFragmentAnalysis(
                fragment_id=f"{document.source_id}__derived_extra",
                artifact_type="mixed_note",
                confidence=0.1,
                title_hint=None,
                canonical_subject=None,
                semantic_class=None,
                promotion_status=None,
                fragment_role=None,
                entities=[],
                topics=[],
                world_terms=[],
                character_refs=[],
                lore_refs=[],
                language=document.dominant_language,
                detected_languages=[document.dominant_language] if document.dominant_language else [],
                register_signals=["llm_candidate_overflow"],
                needs_review=True,
                notes=["llm_candidate_count_exceeds_source_fragments"],
            )
        )
    if not analyses:
        analyses.append(
            BootstrapFragmentAnalysis(
                fragment_id=f"{document.source_id}__frag_001",
                artifact_type="mixed_note",
                confidence=0.0,
                title_hint=None,
                canonical_subject=None,
                semantic_class=None,
                promotion_status=None,
                fragment_role=None,
                entities=[],
                topics=[],
                world_terms=[],
                character_refs=[],
                lore_refs=[],
                language=document.dominant_language,
                detected_languages=[document.dominant_language] if document.dominant_language else [],
                register_signals=["empty"],
                needs_review=True,
                notes=["no_recovered_fragments"],
            )
        )
    return analyses


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
                canonical_subject=_clean_text(raw.get("canonical_subject")),
                semantic_class=_clean_text(raw.get("semantic_class")),
                promotion_status=_clean_text(raw.get("promotion_status")),
                fragment_role=_clean_text(raw.get("fragment_role")),
                entities=_normalize_string_list(raw.get("entities")),
                topics=_normalize_string_list(raw.get("topics")),
                world_terms=_normalize_string_list(raw.get("world_terms")),
                character_refs=_normalize_string_list(raw.get("character_refs")),
                lore_refs=_normalize_string_list(raw.get("lore_refs")),
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
        source_format=document.extension,
        extraction_mode="native_text",
        extraction_confidence=_coerce_confidence(payload.get("confidence")),
        structural_confidence=_coerce_confidence(payload.get("confidence")),
        llm_used=True,
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


def _should_batch_document(*, text: str, fragments: list[SourceFragment]) -> bool:
    if len(fragments) > 8:
        return True
    if len(text) > 12000:
        return True
    return False


def _batched_fragments(fragments: list[SourceFragment], *, batch_size: int = 6) -> list[list[SourceFragment]]:
    return [fragments[index : index + batch_size] for index in range(0, len(fragments), batch_size)]


def _text_for_fragments(fragments: list[SourceFragment]) -> str:
    return "\n\n".join(fragment.text.strip() for fragment in fragments if fragment.text.strip())


def _merge_document_analyses(
    *,
    document: SourceDocumentRecord,
    analyses: list[BootstrapDocumentAnalysis],
    total_fragments: list[SourceFragment],
) -> BootstrapDocumentAnalysis:
    fragment_analyses: list[BootstrapFragmentAnalysis] = []
    seen_fragment_ids: set[str] = set()
    detected_languages: list[str] = []
    coverage_notes: list[str] = []
    unmapped_fragment_ids: list[str] = []
    ambiguous_fragment_ids: list[str] = []
    raw_payloads: list[dict[str, Any]] = []
    confidence_values: list[float] = []
    for analysis in analyses:
        if analysis.dominant_language:
            detected_languages.append(analysis.dominant_language)
        detected_languages.extend(analysis.detected_languages)
        coverage_notes.extend(analysis.coverage_notes)
        unmapped_fragment_ids.extend(analysis.unmapped_fragment_ids)
        ambiguous_fragment_ids.extend(analysis.ambiguous_fragment_ids)
        raw_payloads.append(dict(analysis.raw_payload))
        confidence_values.append(analysis.confidence)
        for fragment_analysis in analysis.fragment_analyses:
            if fragment_analysis.fragment_id in seen_fragment_ids:
                continue
            seen_fragment_ids.add(fragment_analysis.fragment_id)
            fragment_analyses.append(fragment_analysis)
    missing_fragment_ids = [
        fragment.fragment_id
        for fragment in total_fragments
        if fragment.fragment_id not in seen_fragment_ids
    ]
    unmapped_fragment_ids.extend(missing_fragment_ids)
    ambiguous_fragment_ids.extend(missing_fragment_ids)
    deduped_languages = _normalize_string_list(detected_languages)
    dominant_language = deduped_languages[0] if deduped_languages else document.dominant_language
    return BootstrapDocumentAnalysis(
        source_id=document.source_id,
        dominant_language=dominant_language,
        source_format=document.extension,
        extraction_mode="native_text",
        extraction_confidence=(sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0,
        structural_confidence=(sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0,
        llm_used=True,
        detected_languages=deduped_languages,
        has_mixed_language=len(deduped_languages) > 1,
        fragment_analyses=fragment_analyses,
        coverage_notes=_normalize_string_list(coverage_notes),
        unmapped_fragment_ids=_normalize_string_list(unmapped_fragment_ids),
        ambiguous_fragment_ids=_normalize_string_list(ambiguous_fragment_ids),
        requires_confirmation=bool(missing_fragment_ids or any(analysis.requires_confirmation for analysis in analyses)),
        confidence=(sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0,
        raw_payload={"batched": True, "batch_count": len(analyses), "payloads": raw_payloads},
    )


def _emit_progress(path: str | None, **payload: Any) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


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
