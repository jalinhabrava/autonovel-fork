from __future__ import annotations

from typing import Protocol

from textifai.author_response.contracts import AnchoredAuthorPrompt, AnchoredAuthorResponse
from textifai.author_response.provider_client import ConfiguredAuthorResponseClient


class AuthorResponseGenerator(Protocol):
    def generate(self, *, prompt: AnchoredAuthorPrompt) -> AnchoredAuthorResponse:
        ...


class TemplateAuthorResponseGenerator:
    def generate(self, *, prompt: AnchoredAuthorPrompt) -> AnchoredAuthorResponse:
        payload = prompt.user_payload
        kind = prompt.semantic_response_kind
        response = _render_response(kind=kind, payload=payload, ready=prompt.response_generation_ready)
        return AnchoredAuthorResponse(
            semantic_response_kind=kind,
            author_facing_response=None,
            response_generation_ready=prompt.response_generation_ready,
            anchored_prompt_payload=prompt.trace_payload(),
            response_support_summary={
                **prompt.response_support_summary,
                "prompt_template_id": prompt.prompt_template_id,
                "prompt_template_version": prompt.prompt_template_version,
                "model_profile_used": prompt.model_profile_used,
            },
            llm_used=False,
            provider_mode="simulated_preview",
            response_generation_mode="simulated_preview",
            response_generation_reason="heuristic_preview_enabled",
            provider_execution_enabled=False,
            provider_execution_mode="disabled",
            provider_model_used=None,
            live_model_response=None,
            simulated_preview_enabled=True,
            simulated_preview_output=response,
        )


class ProviderBackedAuthorResponseGenerator:
    def __init__(
        self,
        *,
        allow_live: bool = False,
        allow_simulated_preview: bool = False,
        fallback_generator: AuthorResponseGenerator | None = None,
        provider_client: ConfiguredAuthorResponseClient | None = None,
    ) -> None:
        self.allow_live = allow_live
        self.allow_simulated_preview = allow_simulated_preview
        self.fallback_generator = fallback_generator or TemplateAuthorResponseGenerator()
        self.provider_client = provider_client or ConfiguredAuthorResponseClient()

    def generate(self, *, prompt: AnchoredAuthorPrompt) -> AnchoredAuthorResponse:
        allow_live_for_prompt = bool(prompt.dynamic_context_payload.get("allow_live_provider", False))
        allow_preview_for_prompt = bool(prompt.dynamic_context_payload.get("allow_simulated_preview", False))
        live_permitted = self.allow_live or allow_live_for_prompt
        preview_permitted = self.allow_simulated_preview or allow_preview_for_prompt
        if not prompt.response_generation_ready:
            return _disabled_response(prompt=prompt, reason="response_not_ready")
        if live_permitted and self.provider_client.is_available(prompt=prompt):
            try:
                live_text, live_model, provider_name = self.provider_client.generate(prompt=prompt)
                return AnchoredAuthorResponse(
                    semantic_response_kind=prompt.semantic_response_kind,
                    author_facing_response=live_text,
                    response_generation_ready=prompt.response_generation_ready,
                    anchored_prompt_payload=prompt.trace_payload(),
                    response_support_summary={
                        **prompt.response_support_summary,
                        "prompt_template_id": prompt.prompt_template_id,
                        "prompt_template_version": prompt.prompt_template_version,
                        "model_profile_used": prompt.model_profile_used,
                        "provider_mode": "live_provider",
                        "provider_name": provider_name,
                        "provider_model_used": live_model,
                    },
                    llm_used=True,
                    provider_mode="live_provider",
                    response_generation_mode="live_provider",
                    response_generation_reason="live_provider_execution",
                    provider_execution_enabled=True,
                    provider_execution_mode="live_provider",
                    provider_model_used=live_model,
                    live_model_response=live_text,
                    simulated_preview_enabled=False,
                    simulated_preview_output=None,
                )
            except Exception as exc:
                if preview_permitted:
                    fallback = self.fallback_generator.generate(prompt=prompt)
                    return AnchoredAuthorResponse(
                        semantic_response_kind=fallback.semantic_response_kind,
                        author_facing_response=None,
                        response_generation_ready=fallback.response_generation_ready,
                        anchored_prompt_payload=fallback.anchored_prompt_payload,
                        response_support_summary={
                            **fallback.response_support_summary,
                            "provider_mode": "simulated_preview",
                            "provider_fallback_reason": str(exc),
                        },
                        llm_used=False,
                        provider_mode="simulated_preview",
                        response_generation_mode="simulated_preview",
                        response_generation_reason="live_provider_failed_preview_fallback",
                        provider_execution_enabled=False,
                        provider_execution_mode="disabled",
                        provider_model_used=None,
                        live_model_response=None,
                        simulated_preview_enabled=True,
                        simulated_preview_output=fallback.simulated_preview_output,
                    )
                return _disabled_response(prompt=prompt, reason=str(exc))
        if preview_permitted:
            fallback = self.fallback_generator.generate(prompt=prompt)
            return AnchoredAuthorResponse(
                semantic_response_kind=fallback.semantic_response_kind,
                author_facing_response=None,
                response_generation_ready=fallback.response_generation_ready,
                anchored_prompt_payload=fallback.anchored_prompt_payload,
                response_support_summary={
                    **fallback.response_support_summary,
                    "provider_mode": "simulated_preview",
                    "provider_fallback_reason": (
                        "live_provider_not_permitted"
                        if not live_permitted
                        else "provider_not_available"
                    ),
                },
                llm_used=False,
                provider_mode="simulated_preview",
                response_generation_mode="simulated_preview",
                response_generation_reason="heuristic_preview_enabled",
                provider_execution_enabled=False,
                provider_execution_mode="disabled",
                provider_model_used=None,
                live_model_response=None,
                simulated_preview_enabled=True,
                simulated_preview_output=fallback.simulated_preview_output,
            )
        return _disabled_response(
            prompt=prompt,
            reason="live_provider_not_permitted" if not live_permitted else "provider_not_available",
        )


def _disabled_response(*, prompt: AnchoredAuthorPrompt, reason: str) -> AnchoredAuthorResponse:
    return AnchoredAuthorResponse(
        semantic_response_kind=prompt.semantic_response_kind,
        author_facing_response=None,
        response_generation_ready=prompt.response_generation_ready,
        anchored_prompt_payload=prompt.trace_payload(),
        response_support_summary={
            **prompt.response_support_summary,
            "prompt_template_id": prompt.prompt_template_id,
            "prompt_template_version": prompt.prompt_template_version,
            "model_profile_used": prompt.model_profile_used,
            "provider_fallback_reason": reason,
        },
        llm_used=False,
        provider_mode="disabled",
        response_generation_mode="disabled",
        response_generation_reason=reason,
        provider_execution_enabled=False,
        provider_execution_mode="disabled",
        provider_model_used=None,
        live_model_response=None,
        simulated_preview_enabled=False,
        simulated_preview_output=None,
    )


def _render_response(*, kind: str, payload: dict, ready: bool) -> str:
    if not ready:
        return _render_clarification(payload)
    if kind == "structuring_suggestion":
        return _render_structuring(payload)
    if kind == "revision_guidance":
        return _render_revision(payload)
    if kind == "canon_answer":
        return _render_canon(payload)
    if kind == "narration_handoff":
        return _render_narration(payload)
    if kind == "contextual_followup_response":
        return _render_followup(payload)
    return _render_clarification(payload)


def _render_structuring(payload: dict) -> str:
    target = _target_label(payload)
    constraints = _natural_join(payload.get("preserve_constraints", []))
    hints = _hint_labels(payload)
    return (
        f"The most useful move is to reorganize {target} around a clearer dramatic progression, "
        f"without dropping {constraints or 'the tension and voice already anchored in the material'}. "
        f"Based on what is already grounded around {hints or 'the relevant material'}, I would delay explicit explanation and let the tension surface through smaller reactions first. "
        "If you want, I can turn that into a beat-by-beat proposal now."
    )


def _render_revision(payload: dict) -> str:
    constraints = _natural_join(payload.get("preserve_constraints", []))
    issues = _natural_join(payload.get("change_signals", []))
    return (
        f"I would treat this as a guided, precise revision. "
        f"The first thing to move is {issues or 'the focus of the passage'}, while preserving {constraints or 'the voice, dynamics, and canon already recovered'}. "
        "The goal is not to rewrite everything, but to adjust only what is necessary so the passage gains clarity without flattening its personality."
    )


def _render_canon(payload: dict) -> str:
    report = payload.get("consistency_report") or {}
    summary = report.get("summary")
    canon = _first_title(payload.get("supporting_canon", []))
    if summary:
        return (
            f"My best judgement right now is that {summary.lower()} "
            f"That reading comes from {canon or 'the canon already recovered'}, so the answer is cautious but not evasive. "
            "If you want, I can split that into what fits cleanly, what is close to conflict, and what still needs confirmation."
        )
    return (
        f"With the support I have, this looks compatible with {canon or 'the validated canon'}, "
        "but I would not push the claim further than what is actually grounded. "
        "I can break down what fits, what strains the canon, and what still needs review."
    )


def _render_narration(payload: dict) -> str:
    target = _target_label(payload)
    constraints = _natural_join(payload.get("preserve_constraints", []))
    return (
        f"There is enough support now to carry {target} into narration. "
        f"I would keep the emotional focus and {constraints or 'the anchored constraints already in play'} as the guide, so the prose keeps both tone and coherence. "
        "If you want, I can turn it into a short handoff that is ready to write from."
    )


def _render_followup(payload: dict) -> str:
    target = _target_label(payload)
    hints = _hint_labels(payload)
    return (
        f"Yes, I am still working on {target}. "
        f"With the continuity I already have around {hints or 'that thread'}, the most useful move is to continue directly into the next editorial decision instead of restarting from scratch. "
        "If you want, I can continue with a concrete proposal in that direction."
    )


def _render_clarification(payload: dict) -> str:
    candidates = payload.get("candidate_targets", [])
    hints = _hint_labels(payload)
    if candidates:
        labels = [f"{item.get('target_type')}:{item.get('target_id')}" for item in candidates[:3]]
        return (
            f"What already looks fairly clear is the editorial problem around {hints or 'this material'}. "
            f"What is still open is which of these targets you want to focus first: {', '.join(labels)}. "
            "If you point me to the main one, I can answer in a much more focused way."
        )
    return (
        "I already have a general sense of what you want to move, but I still need the minimum anchor to answer well. "
        "If you give me the passage, the exact note, or the concrete target, I can turn it around as a useful editorial answer."
    )


def _target_label(payload: dict) -> str:
    target = payload.get("resolved_target") or {}
    target_type = target.get("target_type")
    target_id = target.get("target_id")
    if target_type and target_id:
        return f"{target_type}:{target_id}"
    return "the already anchored material"


def _first_title(items: list[dict]) -> str | None:
    for item in items:
        title = item.get("title")
        if title:
            return str(title)
    return None


def _natural_join(values: list[str]) -> str:
    filtered = [str(value).replace("_", " ") for value in values if value]
    if not filtered:
        return ""
    if len(filtered) == 1:
        return filtered[0]
    return ", ".join(filtered[:-1]) + f" and {filtered[-1]}"


def _hint_labels(payload: dict) -> str:
    labels: list[str] = []
    for hint in payload.get("entity_hints", [])[:3]:
        if isinstance(hint, dict):
            text = hint.get("hint_text") or hint.get("normalized_hint")
            if text:
                labels.append(str(text))
    if not labels:
        for item in payload.get("candidate_targets", [])[:2]:
            if isinstance(item, dict) and item.get("target_id"):
                labels.append(str(item.get("target_id")))
    return _natural_join(labels)
