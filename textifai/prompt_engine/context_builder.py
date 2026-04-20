from __future__ import annotations

from dataclasses import asdict
from typing import Any

from textifai.conversation.contracts import ConversationRequest, PlannedTask
from textifai.editorial.contracts import EditorialStructuringResult
from textifai.editorial_intent.contracts import EditorialIntent
from textifai.followthrough.contracts import FollowThroughResult
from textifai.prompt_engine.contracts import SemanticPromptContext


def build_semantic_prompt_context(
    *,
    request: ConversationRequest,
    task: PlannedTask,
    semantic_flow_name: str,
    semantic_response_kind: str,
    author_understanding: dict[str, Any] | None,
    editorial_intent: EditorialIntent | None,
    entity_results: list[dict[str, Any]],
    vault_context_snippets: list[dict[str, str]],
    supporting_canon: list[dict[str, str]],
    response_generation_ready: bool,
    exact_artifact_resolution: bool,
    semantic_working_sufficiency: bool,
    general_editorial_sufficiency: bool | None = None,
    anchored_editorial_sufficiency: bool | None = None,
    structuring_result: EditorialStructuringResult | None = None,
    followthrough_result: FollowThroughResult | None = None,
    consistency_report: dict[str, Any] | None = None,
    clarification_payload: dict[str, Any] | None = None,
    response_support_summary_extra: dict[str, Any] | None = None,
) -> SemanticPromptContext:
    general_editorial_sufficiency = (
        semantic_working_sufficiency if general_editorial_sufficiency is None else general_editorial_sufficiency
    )
    anchored_editorial_sufficiency = (
        semantic_working_sufficiency if anchored_editorial_sufficiency is None else anchored_editorial_sufficiency
    )
    resolved_target = None
    candidate_targets: list[dict[str, Any]] = []
    if editorial_intent is not None:
        resolved_target = {
            "target_type": editorial_intent.resolved_target_type,
            "target_id": editorial_intent.resolved_target_id,
        }
        candidate_targets = [
            {
                "target_type": candidate.target_type,
                "target_id": candidate.target_id,
                "confidence": candidate.confidence,
                "supporting_hints": list(getattr(candidate, "supporting_hints", []) or []),
            }
            for candidate in editorial_intent.candidate_targets
        ]
    diagnosis = dict(author_understanding.get("editorial_diagnosis") or {}) if author_understanding else {}

    context_payload = {
        "author_request_text_original": request.raw_text,
        "allow_live_provider": bool(
            request.metadata.get("allow_live_author_response")
            or request.metadata.get("allow_live_provider")
        ),
        "allow_simulated_preview": bool(request.metadata.get("allow_simulated_preview")),
        "provider_name": request.metadata.get("provider_name"),
        "operation_language": task.operation_language,
        "response_language": task.explanation_language,
        "artifact_target_language": task.artifact_target_language,
        "intent_normalized": author_understanding.get("primary_intent_type") if author_understanding else None,
        "flow_name": semantic_flow_name,
        "semantic_response_kind": semantic_response_kind,
        "editorial_diagnosis": diagnosis,
        "response_generation_ready": response_generation_ready,
        "exact_artifact_resolution": exact_artifact_resolution,
        "semantic_working_sufficiency": semantic_working_sufficiency,
        "general_editorial_sufficiency": general_editorial_sufficiency,
        "anchored_editorial_sufficiency": anchored_editorial_sufficiency,
        "editorial_goals": list(editorial_intent.editorial_goals) if editorial_intent else [],
        "preserve_constraints": list(editorial_intent.preserve_constraints) if editorial_intent else [],
        "change_signals": list(author_understanding.get("change_signals", [])) if author_understanding else [],
        "entity_hints": list(author_understanding.get("entity_hints", [])) if author_understanding else [],
        "resolved_target": resolved_target,
        "candidate_targets": candidate_targets,
        "followup_mode": editorial_intent.followup_mode if editorial_intent else None,
        "vault_context_snippets": vault_context_snippets,
        "supporting_canon": supporting_canon,
        "vaerl_results": entity_results,
        "structuring_result": _serialize_structuring_result(structuring_result),
        "followthrough_result": _serialize_followthrough_result(followthrough_result),
        "consistency_report": consistency_report,
        "clarification_payload": clarification_payload,
        "recent_context": {
            "phase_classification": task.metadata.get("phase_classification"),
            "response_generation_candidate": task.metadata.get("response_generation_candidate"),
        },
    }

    llm_context_payload = {
        "author_request_text_original": request.raw_text,
        "system_interpretation": _system_interpretation(
            semantic_flow_name=semantic_flow_name,
            editorial_intent=editorial_intent,
            author_understanding=author_understanding,
            response_language=task.explanation_language,
            diagnosis=diagnosis,
        ),
        "flow_goal": _flow_goal(semantic_flow_name, response_language=task.explanation_language),
        "response_language": task.explanation_language,
        "artifact_target_language": task.artifact_target_language,
        "exact_artifact_resolution": exact_artifact_resolution,
        "general_editorial_sufficiency": general_editorial_sufficiency,
        "anchored_editorial_sufficiency": anchored_editorial_sufficiency,
        "best_candidate_targets": _best_candidate_targets(resolved_target, candidate_targets),
        "editorial_diagnosis": _editorial_diagnosis_summary(diagnosis, response_language=task.explanation_language),
        "preserve_constraints": _editorialize_labels(list(editorial_intent.preserve_constraints) if editorial_intent else []),
        "editorial_goals": _editorialize_labels(list(editorial_intent.editorial_goals) if editorial_intent else []),
        "change_signals": _editorialize_labels(list(author_understanding.get("change_signals", [])) if author_understanding else []),
        "anchored_context_summary": _anchored_context_summary(vault_context_snippets),
        "supporting_canon_summary": _canon_summary(supporting_canon),
        "narrative_state_summary": _narrative_state_summary(
            structuring_result=structuring_result,
            followthrough_result=followthrough_result,
            consistency_report=consistency_report,
            response_language=task.explanation_language,
        ),
        "clarification_need": _clarification_need(
            clarification_payload=clarification_payload,
            resolved_target=resolved_target,
            candidate_targets=candidate_targets,
            general_editorial_sufficiency=general_editorial_sufficiency,
            anchored_editorial_sufficiency=anchored_editorial_sufficiency,
            response_language=task.explanation_language,
            diagnosis=diagnosis,
        ),
    }

    anchored_evidence_used = {
        "resolved_target": resolved_target,
        "candidate_targets": candidate_targets[:3],
        "vault_context_snippets": vault_context_snippets,
        "supporting_canon": supporting_canon,
        "vaerl_results": entity_results,
    }
    response_support_summary = {
        "resolved_target": resolved_target,
        "exact_artifact_resolution": exact_artifact_resolution,
        "semantic_working_sufficiency": semantic_working_sufficiency,
        "general_editorial_sufficiency": general_editorial_sufficiency,
        "anchored_editorial_sufficiency": anchored_editorial_sufficiency,
        "followthrough_from_previous_turn": followthrough_result is not None,
        "candidate_target_count": len(candidate_targets),
        "vault_context_count": len(vault_context_snippets),
        "supporting_canon_count": len(supporting_canon),
        "has_structuring_result": structuring_result is not None,
        "has_followthrough_result": followthrough_result is not None,
        "has_consistency_report": consistency_report is not None,
        "has_clarification_payload": clarification_payload is not None,
    }
    if response_support_summary_extra:
        response_support_summary.update(response_support_summary_extra)

    return SemanticPromptContext(
        semantic_flow_name=semantic_flow_name,
        semantic_response_kind=semantic_response_kind,
        request_text=request.raw_text,
        operation_language=task.operation_language,
        response_language=task.explanation_language,
        artifact_target_language=task.artifact_target_language,
        context_payload=context_payload,
        llm_context_payload=llm_context_payload,
        anchored_evidence_used=anchored_evidence_used,
        response_support_summary=response_support_summary,
    )


def _serialize_structuring_result(result: EditorialStructuringResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "result_kind": result.result_kind,
        "ready_for_validation": result.ready_for_validation,
        "story_facts": asdict(result.story_facts) if result.story_facts is not None else None,
        "beat_outline": asdict(result.beat_outline) if result.beat_outline is not None else None,
        "revision_intent": asdict(result.revision_intent) if result.revision_intent is not None else None,
        "narration_prep": asdict(result.narration_prep) if result.narration_prep is not None else None,
    }


def _serialize_followthrough_result(result: FollowThroughResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return asdict(result)


def _flow_goal(semantic_flow_name: str, *, response_language: str) -> str:
    goals_en = {
        "structuring_request": "Help the author make the next structural narrative decision.",
        "editorial_revision": "Help the author revise with precision while preserving voice and dynamics.",
        "consistency_check": "Give the author the best current canon judgement.",
        "prepare_narration": "Hand off the material in a way that is ready to write from.",
        "contextual_followup": "Continue the current editorial thread without resetting the conversation.",
        "clarification_with_candidates": "Clarify naturally and ask for the minimum needed to focus the answer.",
    }
    goals_es = {
        "structuring_request": "Ayudar al autor a tomar la siguiente decisión estructural de la escena.",
        "editorial_revision": "Ayudar al autor a revisar con precisión, preservando voz y dinámica.",
        "consistency_check": "Dar al autor el mejor juicio actual sobre canon y consistencia.",
        "prepare_narration": "Entregar el material de una forma que ya sirva como handoff para narrar.",
        "contextual_followup": "Continuar el hilo editorial actual sin reiniciar la conversación.",
        "clarification_with_candidates": "Aclarar de forma natural y pedir solo lo mínimo necesario para enfocar la respuesta.",
    }
    goals = goals_es if _is_spanish(response_language) else goals_en
    fallback = (
        "Ayudar al autor a tomar la siguiente buena decisión narrativa."
        if _is_spanish(response_language)
        else "Help the author make the next good narrative decision."
    )
    return goals.get(semantic_flow_name, fallback)


def _best_candidate_targets(resolved_target: dict[str, Any] | None, candidate_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    if resolved_target and resolved_target.get("target_type") and resolved_target.get("target_id"):
        selected.append(dict(resolved_target))
    for candidate in candidate_targets[:3]:
        selected.append(
            {
                "target_type": candidate.get("target_type"),
                "target_id": candidate.get("target_id"),
                "confidence": candidate.get("confidence"),
            }
        )
    return selected


def _anchored_context_summary(vault_context_snippets: list[dict[str, str]]) -> list[str]:
    summaries: list[str] = []
    for item in vault_context_snippets[:4]:
        title = item.get("title") or f"{item.get('artifact_type')}:{item.get('artifact_id')}"
        excerpt = " ".join(str(item.get("excerpt", "")).split())
        summaries.append(f"{title}: {excerpt[:220]}".strip())
    return summaries


def _canon_summary(supporting_canon: list[dict[str, str]]) -> list[str]:
    summaries: list[str] = []
    for item in supporting_canon[:3]:
        title = item.get("title") or f"{item.get('artifact_type')}:{item.get('artifact_id')}"
        excerpt = " ".join(str(item.get("excerpt", "")).split())
        summaries.append(f"{title}: {excerpt[:220]}".strip())
    return summaries


def _narrative_state_summary(
    *,
    structuring_result: EditorialStructuringResult | None,
    followthrough_result: FollowThroughResult | None,
    consistency_report: dict[str, Any] | None,
    response_language: str,
) -> dict[str, Any]:
    if structuring_result is not None:
        return {
            "result_kind": structuring_result.result_kind,
            "has_story_facts": bool(structuring_result.story_facts and structuring_result.story_facts.explicit_facts),
            "has_beat_outline": bool(structuring_result.beat_outline and structuring_result.beat_outline.beats),
            "has_revision_intent": structuring_result.revision_intent is not None,
            "has_narration_prep": structuring_result.narration_prep is not None,
        }
    if followthrough_result is not None:
        return {
            "next_recommended_step": followthrough_result.next_recommended_step,
            "ready_for_user_confirmation": followthrough_result.ready_for_user_confirmation,
            "has_validated_state": followthrough_result.validated_structuring_state is not None,
            "followthrough_from_previous_turn": True,
            "context_origin": (
                "deriva de un turno anterior ya validado"
                if _is_spanish(response_language)
                else "derived from a previously validated turn"
            ),
        }
    if consistency_report is not None:
        return {
            "summary": consistency_report.get("summary"),
            "status": consistency_report.get("status"),
        }
    return {}


def _clarification_need(
    *,
    clarification_payload: dict[str, Any] | None,
    resolved_target: dict[str, Any] | None,
    candidate_targets: list[dict[str, Any]],
    general_editorial_sufficiency: bool,
    anchored_editorial_sufficiency: bool,
    response_language: str,
    diagnosis: dict[str, Any],
) -> dict[str, Any]:
    open_but_non_blocking = _open_non_blocking_points(diagnosis, response_language=response_language)
    if clarification_payload is None:
        if anchored_editorial_sufficiency:
            return {
                "required": False,
                "can_answer_now": True,
                "clear_now": (
                    "Ya hay soporte anclado suficiente para responder de forma concreta sobre el material recuperado."
                    if _is_spanish(response_language)
                    else "There is enough anchored support to answer concretely about the recovered material."
                ),
                "still_ambiguous": None,
                "open_but_non_blocking": open_but_non_blocking,
                "minimum_needed": None,
            }
        if general_editorial_sufficiency:
            return {
                "required": False,
                "can_answer_now": True,
                "clear_now": (
                    "El problema editorial ya está lo bastante claro como para dar una orientación útil."
                    if _is_spanish(response_language)
                    else "The editorial problem is clear enough for useful guidance."
                ),
                "still_ambiguous": (
                    "Todavía no está del todo fijado el pasaje o artefacto exacto."
                    if _is_spanish(response_language)
                    else "The exact passage or artifact is not fully pinned down yet."
                ),
                "open_but_non_blocking": open_but_non_blocking,
                "minimum_needed": (
                    "Nombra el pasaje o la nota solo si quieres una respuesta más anclada al material concreto."
                    if _is_spanish(response_language)
                    else "Name the passage or note only if you want a more tightly anchored answer."
                ),
            }
        return {
            "required": False,
            "can_answer_now": True,
            "clear_now": (
                "Ya hay soporte suficiente para dar una respuesta útil."
                if _is_spanish(response_language)
                else "There is enough support to give a useful author-facing answer."
            ),
            "still_ambiguous": None,
            "open_but_non_blocking": open_but_non_blocking,
            "minimum_needed": None,
        }
    reason = clarification_payload.get("reason") or "material ambiguity"
    return {
        "required": not general_editorial_sufficiency,
        "can_answer_now": bool(general_editorial_sufficiency),
        "clear_now": (
            "El problema editorial ya está bastante claro."
            if _is_spanish(response_language) and (candidate_targets or general_editorial_sufficiency)
            else "La petición se entiende a nivel general."
            if _is_spanish(response_language)
            else "The editorial problem is already fairly clear."
            if candidate_targets or general_editorial_sufficiency
            else "The request is understood at a high level."
        ),
        "still_ambiguous": (
            reason
            if not resolved_target or not resolved_target.get("target_id")
            else (
                "El foco exacto todavía no está del todo acotado."
                if _is_spanish(response_language)
                else "The exact focus is still not fully narrowed."
            )
        ),
        "open_but_non_blocking": open_but_non_blocking,
        "minimum_needed": clarification_payload.get("next_step") or (
            "Una confirmación mínima del target o un fragmento breve del pasaje."
            if _is_spanish(response_language)
            else "A minimal target confirmation or short passage excerpt."
        ),
    }


EDITORIAL_LABEL_MAP = {
    "structure_scene": "ordenar mejor la progresion de la escena",
    "prepare_for_review": "dejar el pasaje listo para una revision fina",
    "prepare_for_narration": "dejar el material listo para narrarlo",
    "preserve_scene_conflict": "mantener la tension y el conflicto ya presentes",
    "preserve_character_voice": "conservar la voz propia del personaje",
    "preserve_validated_canon": "respetar el canon ya validado",
    "anchor_canon": "comprobar el encaje con el canon anclado",
    "preserve_relational_coherence": "mantener la coherencia del vínculo y de la dinámica relacional",
    "shape_comedic_scene_with_relational_subtext": "estructurar una escena ligera donde la comedia visible sostenga un avance afectivo implícito",
    "choose_dual_effect_closing_beat": "decidir un beat final con doble efecto: remate cómico arriba y avance afectivo abajo",
    "revise_voice_and_relational_dynamic": "revisar voz y dinámica relacional sin volver genérico el pasaje",
    "control_subtext_explicitness": "controlar cuánto del subtexto se vuelve explícito",
    "guide_sera_intimate_but_guarded_voice": "hacer que Sera baje un poco la guardia sin dejar de sonar intensa, orgullosa y contenida",
    "preserve_ren_care_pattern": "preservar el patrón de Ren como cuidado silencioso con ironía suave",
    "control_closeness_without_confession": "hacer avanzar la cercanía sin convertirla en confesión abierta",
    "balance_light_tone_with_relational_weight": "mantener ligereza tonal sin perder peso relacional",
    "evaluate_symbolic_canon_link": "evaluar si la conexión simbólica propuesta puede sostenerse dentro del canon",
    "test_deformed_historical_continuity": "comprobar si hay una continuidad histórica deformada y no solo una coincidencia casual",
    "separate_plausible_symbolism_from_hard_canon": "distinguir una resonancia simbólica plausible de una afirmación dura de canon",
}


def _editorialize_labels(values: list[str]) -> list[str]:
    rendered: list[str] = []
    for value in values:
        if not value:
            continue
        rendered.append(EDITORIAL_LABEL_MAP.get(value, str(value).replace("_", " ")))
    return rendered


def _system_interpretation(
    *,
    semantic_flow_name: str,
    editorial_intent,
    author_understanding: dict[str, Any] | None,
    response_language: str,
    diagnosis: dict[str, Any],
) -> str:
    intent_type = None
    if author_understanding:
        intent_type = author_understanding.get("primary_intent_type")
    request_type = editorial_intent.request_type if editorial_intent is not None else intent_type or semantic_flow_name
    if _is_spanish(response_language):
        dominant_need = diagnosis.get("dominant_need")
        if dominant_need == "structuring_tonal_relational":
            return (
                "Flujo semántico actual: structuring_request. "
                "La necesidad dominante parece ser una estructuración ligera con doble plano: efecto tonal o cómico visible y avance relacional implícito."
            )
        if dominant_need == "voice_revision_relational":
            return (
                "Flujo semántico actual: editorial_revision. "
                "La necesidad dominante parece ser una revisión fina de voz y dinámica relacional, con control del subtexto y de la explicitud."
            )
        if dominant_need == "canon_symbolic_fit":
            return (
                "Flujo semántico actual: consistency_check. "
                "La necesidad dominante parece ser un juicio canon-editorial sobre si una intuición simbólica puede sostenerse sin forzar el lore."
            )
        if semantic_flow_name == "clarification_with_candidates":
            return (
                "Flujo semántico actual: clarification_with_candidates. "
                f"Se ha interpretado la petición como {request_type}, pero todavía hay que acotar mejor el foco entre candidatos plausibles."
            )
        if semantic_flow_name == "contextual_followup":
            return (
                "Flujo semántico actual: contextual_followup. "
                f"Se ha interpretado la petición como {request_type} y se está reutilizando continuidad conversacional reciente."
            )
        return f"Flujo semántico actual: {semantic_flow_name}. Tipo de petición interpretado: {request_type}."
    if semantic_flow_name == "clarification_with_candidates":
        return (
            "Current semantic flow: clarification_with_candidates. "
            f"The request reads as {request_type}, but the focus still needs narrowing across plausible candidates."
        )
    return f"Current semantic flow: {semantic_flow_name}. Interpreted request type: {request_type}."


def _is_spanish(language: str | None) -> bool:
    if not language:
        return False
    return str(language).lower().startswith("es")


def _editorial_diagnosis_summary(diagnosis: dict[str, Any], *, response_language: str) -> dict[str, Any]:
    if not diagnosis:
        return {}
    dominant_need = diagnosis.get("dominant_need")
    if _is_spanish(response_language):
        dominant_map = {
            "structuring_tonal_relational": "estructuración tonal y relacional con subtexto",
            "voice_revision_relational": "revisión fina de voz y dinámica relacional",
            "canon_symbolic_fit": "evaluación de encaje canon-simbólico",
            "general_editorial_guidance": "orientación editorial general",
        }
    else:
        dominant_map = {
            "structuring_tonal_relational": "tonal-relational structuring with subtext",
            "voice_revision_relational": "fine-grained voice and relational revision",
            "canon_symbolic_fit": "canon-symbolic fit evaluation",
            "general_editorial_guidance": "general editorial guidance",
        }
    return {
        "dominant_need": dominant_map.get(dominant_need, dominant_need),
        "secondary_needs": list(diagnosis.get("secondary_needs") or []),
        "diagnostic_signals": list(diagnosis.get("diagnostic_signals") or []),
        "is_editorial_metacommentary": bool(diagnosis.get("is_editorial_metacommentary")),
    }


def _open_non_blocking_points(diagnosis: dict[str, Any], *, response_language: str) -> list[str]:
    dominant_need = diagnosis.get("dominant_need")
    if dominant_need == "structuring_tonal_relational":
        return [
            "El beat final exacto puede afinarse más adelante sin bloquear una orientación estructural útil."
            if _is_spanish(response_language)
            else "The exact closing beat can be refined later without blocking useful structural guidance."
        ]
    if dominant_need == "voice_revision_relational":
        return [
            "La formulación verbal exacta puede decidirse más tarde mientras ya se preserve el patrón relacional."
            if _is_spanish(response_language)
            else "The exact wording can be decided later as long as the relational pattern is preserved."
        ]
    if dominant_need == "canon_symbolic_fit":
        return [
            "Todavía puede quedar por decidir si la conexión se formula como eco simbólico o como continuidad histórica más fuerte."
            if _is_spanish(response_language)
            else "It may still need clarification whether the link is framed as symbolic echo or as stronger historical continuity."
        ]
    return []
