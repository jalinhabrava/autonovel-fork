import unittest

from textifai.author_response.prompt_builder import build_anchored_author_prompt
from textifai.conversation.contracts import ConversationRequest, PlannedTask
from textifai.editorial_intent.contracts import CandidateTarget, EditorialIntent
from textifai.prompt_engine.template_loader import load_model_profile, load_prompt_base, load_prompt_template
from textifai.vaerl.contracts import EntityHint


class TextifAISemanticPromptEngineTests(unittest.TestCase):
    def test_loads_explicit_template_and_model_profile(self):
        prompt_base = load_prompt_base()
        template = load_prompt_template("structuring_request")
        profile = load_model_profile("openai_chatgpt")

        self.assertEqual(prompt_base.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(template.prompt_template_id, "structuring_request")
        self.assertEqual(template.semantic_response_kind, "structuring_suggestion")
        self.assertEqual(profile.model_profile_id, "openai_chatgpt")
        self.assertIn("objective", profile.instruction_order)

    def test_builds_rendered_prompt_with_traceable_metadata(self):
        prompt = build_anchored_author_prompt(
            request=_request("Quiero estructurar esta escena sin perder la tension."),
            task=_task(),
            semantic_response_kind="structuring_suggestion",
            response_generation_ready=True,
            exact_artifact_resolution=True,
            semantic_working_sufficiency=True,
            author_understanding={
                "primary_intent_type": "structuring_request",
                "change_signals": ["clarity_issue"],
                "entity_hints": [{"hint_text": "Ren", "confidence": 0.9}],
            },
            editorial_intent=_editorial_intent(),
            entity_results=[
                {
                    "resolved": True,
                    "resolved_entity_type": "scene",
                    "resolved_entity_id": "scene_12",
                }
            ],
            vault_context_snippets=[
                {"artifact_type": "scene", "artifact_id": "scene_12", "title": "Scene 12", "excerpt": "Tension rises.", "source": "resolved_target", "path": "/tmp/scene_12.md"}
            ],
            supporting_canon=[
                {"artifact_type": "lore", "artifact_id": "spelarita", "title": "Spelarita", "excerpt": "Canon note.", "source": "linked_lore", "path": "/tmp/spelarita.md"}
            ],
        )

        trace = prompt.trace_payload()
        self.assertEqual(prompt.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(prompt.prompt_template_id, "structuring_request")
        self.assertEqual(prompt.prompt_template_version, "v1")
        self.assertEqual(prompt.model_profile_used, "openai_chatgpt")
        self.assertEqual(trace["semantic_flow_name"], "structuring_request")
        self.assertIn("system_prompt", trace["trace_rendered_prompt_payload"])
        self.assertIn("user_payload", trace["trace_rendered_prompt_payload"])
        self.assertIn("user_payload", trace["llm_rendered_prompt_payload"])
        self.assertEqual(trace["dynamic_context_payload"]["resolved_target"]["target_id"], "scene_12")
        self.assertTrue(trace["dynamic_context_payload"]["exact_artifact_resolution"])
        self.assertEqual(trace["anchored_evidence_used"]["supporting_canon"][0]["artifact_id"], "spelarita")
        self.assertIn("anchored_context_summary", trace["llm_rendered_prompt_payload"]["user_payload"])
        self.assertEqual(
            trace["llm_rendered_prompt_payload"]["user_payload"]["editorial_goals"][0],
            "ordenar mejor la progresion de la escena",
        )
        self.assertEqual(
            trace["llm_rendered_prompt_payload"]["user_payload"]["preserve_constraints"][0],
            "mantener la tension y el conflicto ya presentes",
        )

    def test_request_can_override_model_profile(self):
        prompt = build_anchored_author_prompt(
            request=_request(
                "Revísame esta escena sin romper la voz.",
                metadata={"model_profile": "qwen"},
            ),
            task=_task(),
            semantic_response_kind="revision_guidance",
            response_generation_ready=True,
            exact_artifact_resolution=True,
            semantic_working_sufficiency=True,
            author_understanding={"primary_intent_type": "editorial_revision", "entity_hints": []},
            editorial_intent=_editorial_intent(request_type="editorial_revision"),
            entity_results=[],
            vault_context_snippets=[],
            supporting_canon=[],
        )
        self.assertEqual(prompt.model_profile_used, "qwen")
        self.assertEqual(prompt.trace_payload()["trace_rendered_prompt_payload"]["explicitness"], "high")


def _request(raw_text: str, *, metadata: dict | None = None) -> ConversationRequest:
    return ConversationRequest(
        raw_text=raw_text,
        source="user",
        mode="normal",
        interface_language="es",
        user_command_language="es",
        internal_system_language="en",
        project_default_language="ja",
        mixed_language_allowed=True,
        artifact_target_language="ja",
        explanation_language="es",
        metadata=dict(metadata or {}),
    )


def _task() -> PlannedTask:
    return PlannedTask(
        task_type="editorial_structuring",
        flow_name="editorial_structuring_flow",
        target_type="scene",
        target_id="scene_12",
        ephemeral=True,
        persistent=False,
        operation_language="es",
        artifact_target_language="ja",
        explanation_language="es",
        requires_context=False,
        requires_llm=False,
        requires_persistence=False,
        semantic_phase=True,
        step_kinds=["return_response"],
        metadata={"phase_classification": "semantic", "response_generation_candidate": True},
    )


def _editorial_intent(*, request_type: str = "structuring_request") -> EditorialIntent:
    return EditorialIntent(
        request_type=request_type,
        confidence=0.92,
        semantic_basis="author_understanding_validated",
        resolved_target_type="scene",
        resolved_target_id="scene_12",
        candidate_targets=[CandidateTarget(target_id="scene_12", target_type="scene", confidence=0.92)],
        entity_hints=[
            EntityHint(
                hint_text="scene 12",
                normalized_hint="scene 12",
                confidence=0.8,
                candidate_target_id="scene_12",
                candidate_target_type="scene",
                supported_by_author_understanding=True,
            )
        ],
        preserve_constraints=["preserve_scene_conflict"],
        editorial_goals=["structure_scene"],
    )


if __name__ == "__main__":
    unittest.main()
