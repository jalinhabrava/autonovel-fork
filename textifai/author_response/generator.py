from __future__ import annotations

from typing import Protocol

from textifai.author_response.contracts import AnchoredAuthorPrompt, AnchoredAuthorResponse
from textifai.author_response.provider_client import OpenAIAuthorResponseClient


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
        openai_client: OpenAIAuthorResponseClient | None = None,
    ) -> None:
        self.allow_live = allow_live
        self.allow_simulated_preview = allow_simulated_preview
        self.fallback_generator = fallback_generator or TemplateAuthorResponseGenerator()
        self.openai_client = openai_client or OpenAIAuthorResponseClient()

    def generate(self, *, prompt: AnchoredAuthorPrompt) -> AnchoredAuthorResponse:
        allow_live_for_prompt = bool(prompt.dynamic_context_payload.get("allow_live_provider", False))
        allow_preview_for_prompt = bool(prompt.dynamic_context_payload.get("allow_simulated_preview", False))
        live_permitted = self.allow_live or allow_live_for_prompt
        preview_permitted = self.allow_simulated_preview or allow_preview_for_prompt
        if not prompt.response_generation_ready:
            return _disabled_response(prompt=prompt, reason="response_not_ready")
        if live_permitted and self.openai_client.is_available():
            try:
                live_text, live_model = self.openai_client.generate(prompt=prompt)
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
                        "provider_mode": "live_openai",
                        "provider_model_used": live_model,
                    },
                    llm_used=True,
                    provider_mode="live_openai",
                    response_generation_mode="live_openai",
                    response_generation_reason="live_provider_execution",
                    provider_execution_enabled=True,
                    provider_execution_mode="live_openai",
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
                        else "missing_openai_api_key"
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
            reason="live_provider_not_permitted" if not live_permitted else "missing_openai_api_key",
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
        f"Aqui lo mas util seria ordenar {target} alrededor de una progresion dramatica mas clara, "
        f"sin soltar {constraints or 'la tension y la voz que ya vienen marcadas'}. "
        f"Con lo que ya tengo anclado sobre {hints or 'el material relevante'}, la mejor macrodecision seria retrasar la explicitud y dejar que la tension se vea en pequenas reacciones, no en explicaciones directas. "
        "Si quieres, te lo convierto ahora en una propuesta beat by beat."
    )


def _render_revision(payload: dict) -> str:
    constraints = _natural_join(payload.get("preserve_constraints", []))
    issues = _natural_join(payload.get("change_signals", []))
    return (
        f"Yo lo enfocaria como una revision guiada y bastante precisa. "
        f"Lo que conviene mover primero es {issues or 'el foco de la escena'}, mientras preservamos {constraints or 'la voz, la dinamica y el canon ya recuperados'}. "
        "La idea no seria reescribirlo todo, sino tocar justo lo necesario para que el pasaje gane claridad sin perder personalidad."
    )


def _render_canon(payload: dict) -> str:
    report = payload.get("consistency_report") or {}
    summary = report.get("summary")
    canon = _first_title(payload.get("supporting_canon", []))
    if summary:
        return (
            f"Mi mejor juicio ahora mismo es que {summary.lower()} "
            f"La lectura sale de {canon or 'el canon recuperado'}, asi que la respuesta es prudente, pero no evasiva. "
            "Si quieres, te lo separo en lo que encaja bien, lo que roza el conflicto y lo que aun pediria confirmacion."
        )
    return (
        f"Con el soporte que tengo, esto parece compatible con {canon or 'el canon validado'}, "
        "aunque no iria mas lejos de lo que realmente esta anclado. "
        "Puedo desglosarte enseguida que encaja, que tensiona el canon y que conviene revisar."
    )


def _render_narration(payload: dict) -> str:
    target = _target_label(payload)
    constraints = _natural_join(payload.get("preserve_constraints", []))
    return (
        f"Ya hay base suficiente para llevar {target} a narracion. "
        f"Yo arrastraria como guia el foco emocional y {constraints or 'las restricciones ya ancladas'}, para que la prosa no pierda ni tono ni coherencia. "
        "Si quieres, te lo dejo en un handoff corto y muy escribible."
    )


def _render_followup(payload: dict) -> str:
    target = _target_label(payload)
    hints = _hint_labels(payload)
    return (
        f"Si, sigo sobre {target}. "
        f"Con la continuidad que ya tengo sobre {hints or 'ese hilo'}, lo mas util es no reiniciar nada y avanzar directamente a la siguiente decision editorial. "
        "Si quieres, continúo con una propuesta concreta en esa misma direccion."
    )


def _render_clarification(payload: dict) -> str:
    candidates = payload.get("candidate_targets", [])
    hints = _hint_labels(payload)
    if candidates:
        labels = [f"{item.get('target_type')}:{item.get('target_id')}" for item in candidates[:3]]
        return (
            f"Lo que si veo ya bastante claro es el problema editorial alrededor de {hints or 'este material'}. "
            f"Lo que sigue abierto es sobre cual de estos focos quieres trabajar primero: {', '.join(labels)}. "
            "Con que me señales cual es el principal, te respondo ya de forma mucho mas enfocada."
        )
    return (
        "Ya tengo una idea general de lo que quieres mover, pero aun me falta el anclaje minimo para responderte bien de verdad. "
        "Si me das el pasaje, la nota concreta o el foco exacto, te lo devuelvo ya en forma editorial y util."
    )


def _target_label(payload: dict) -> str:
    target = payload.get("resolved_target") or {}
    target_type = target.get("target_type")
    target_id = target.get("target_id")
    if target_type and target_id:
        return f"{target_type}:{target_id}"
    return "el material ya anclado"


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
    return ", ".join(filtered[:-1]) + f" y {filtered[-1]}"


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
