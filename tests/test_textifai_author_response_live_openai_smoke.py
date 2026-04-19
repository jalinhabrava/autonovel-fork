import os
import unittest

from textifai.author_response.prompt_builder import build_anchored_author_prompt
from textifai.author_response.generator import ProviderBackedAuthorResponseGenerator, TemplateAuthorResponseGenerator
from textifai.conversation.contracts import ConversationRequest, PlannedTask
from textifai.editorial_intent.contracts import EditorialIntent


@unittest.skipUnless(os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
class TextifAIAuthorResponseLiveOpenAISmokeTests(unittest.TestCase):
    def test_live_openai_generates_author_facing_response(self):
        generator = ProviderBackedAuthorResponseGenerator(
            allow_live=True,
            fallback_generator=TemplateAuthorResponseGenerator(),
        )
        prompt = build_anchored_author_prompt(
            request=_request(),
            task=_task(),
            semantic_response_kind="revision_guidance",
            response_generation_ready=True,
            author_understanding={"primary_intent_type": "editorial_revision", "change_signals": ["tone_issue"], "entity_hints": []},
            editorial_intent=EditorialIntent(
                request_type="editorial_revision",
                confidence=0.9,
                semantic_basis="author_understanding_validated",
                resolved_target_type="scene",
                resolved_target_id="scene_12",
                preserve_constraints=["preserve_scene_conflict"],
                editorial_goals=["align_tone"],
            ),
            entity_results=[],
            vault_context_snippets=[
                {"artifact_type": "scene", "artifact_id": "scene_12", "title": "Scene 12", "excerpt": "A tense exchange between two characters.", "source": "resolved_target", "path": "/tmp/scene_12.md"}
            ],
            supporting_canon=[],
        )

        response = generator.generate(prompt=prompt)

        self.assertEqual(response.provider_mode, "live_openai")
        self.assertTrue(bool(response.provider_model_used))
        self.assertTrue(bool(response.live_model_response))
        self.assertTrue(bool(response.author_facing_response))


def _request() -> ConversationRequest:
    return ConversationRequest(
        raw_text="Revísame esta escena sin romper la tensión.",
        source="user",
        mode="normal",
        interface_language="es",
        user_command_language="es",
        internal_system_language="en",
        project_default_language="ja",
        mixed_language_allowed=True,
        artifact_target_language="ja",
        explanation_language="es",
        metadata={"allow_live_author_response": True},
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


if __name__ == "__main__":
    unittest.main()
