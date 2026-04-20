import unittest
from unittest.mock import Mock
from unittest.mock import patch

from textifai.author_response.contracts import AnchoredAuthorPrompt
from textifai.author_response.generator import ProviderBackedAuthorResponseGenerator, TemplateAuthorResponseGenerator


class TextifAIAuthorResponseProviderTests(unittest.TestCase):
    def test_falls_back_to_simulated_when_live_not_permitted(self):
        generator = ProviderBackedAuthorResponseGenerator(
            allow_live=False,
            allow_simulated_preview=False,
            fallback_generator=TemplateAuthorResponseGenerator(),
        )
        prompt = _prompt(allow_live_provider=False, ready=True)

        response = generator.generate(prompt=prompt)

        self.assertEqual(response.provider_mode, "disabled")
        self.assertIsNone(response.author_facing_response)
        self.assertFalse(response.simulated_preview_enabled)
        self.assertIsNone(response.provider_model_used)
        self.assertIsNone(response.live_model_response)
        self.assertEqual(response.response_support_summary.get("provider_fallback_reason"), "live_provider_not_permitted")

    def test_falls_back_to_simulated_when_key_missing(self):
        generator = ProviderBackedAuthorResponseGenerator(
            allow_live=True,
            allow_simulated_preview=False,
            fallback_generator=TemplateAuthorResponseGenerator(),
        )
        prompt = _prompt(allow_live_provider=True, ready=True)

        with patch.dict("os.environ", {"AUTONOVEL_TEXT_PROVIDER": "openai", "OPENAI_API_KEY": ""}, clear=False):
            response = generator.generate(prompt=prompt)

        self.assertEqual(response.provider_mode, "disabled")
        self.assertEqual(response.response_generation_mode, "disabled")
        self.assertEqual(response.response_support_summary.get("provider_fallback_reason"), "provider_not_available")

    def test_uses_live_provider_when_permitted_and_available(self):
        fake_client = Mock()
        fake_client.is_available.return_value = True
        fake_client.generate.return_value = ("Live answer from model.", "gpt-test", "anthropic")
        generator = ProviderBackedAuthorResponseGenerator(
            allow_live=True,
            allow_simulated_preview=False,
            fallback_generator=TemplateAuthorResponseGenerator(),
            provider_client=fake_client,
        )

        response = generator.generate(prompt=_prompt(allow_live_provider=True, ready=True))

        self.assertEqual(response.provider_mode, "live_provider")
        self.assertTrue(response.provider_execution_enabled)
        self.assertEqual(response.provider_execution_mode, "live_provider")
        self.assertEqual(response.provider_model_used, "gpt-test")
        self.assertEqual(response.live_model_response, "Live answer from model.")
        self.assertEqual(response.author_facing_response, "Live answer from model.")
        self.assertEqual(response.response_support_summary.get("provider_mode"), "live_provider")
        self.assertEqual(response.response_support_summary.get("provider_name"), "anthropic")

    def test_not_ready_stays_conservative_even_if_live_is_available(self):
        fake_client = Mock()
        fake_client.is_available.return_value = True
        generator = ProviderBackedAuthorResponseGenerator(
            allow_live=True,
            allow_simulated_preview=False,
            fallback_generator=TemplateAuthorResponseGenerator(),
            provider_client=fake_client,
        )

        response = generator.generate(prompt=_prompt(allow_live_provider=True, ready=False))

        self.assertEqual(response.provider_mode, "disabled")
        self.assertEqual(response.response_support_summary.get("provider_fallback_reason"), "response_not_ready")
        fake_client.generate.assert_not_called()

    def test_can_emit_simulated_preview_when_explicitly_enabled(self):
        generator = ProviderBackedAuthorResponseGenerator(
            allow_live=False,
            allow_simulated_preview=True,
            fallback_generator=TemplateAuthorResponseGenerator(),
        )

        response = generator.generate(prompt=_prompt(allow_live_provider=False, ready=True))

        self.assertEqual(response.provider_mode, "simulated_preview")
        self.assertIsNone(response.author_facing_response)
        self.assertTrue(response.simulated_preview_enabled)
        self.assertTrue(bool(response.simulated_preview_output))


def _prompt(*, allow_live_provider: bool, ready: bool) -> AnchoredAuthorPrompt:
    return AnchoredAuthorPrompt(
        prompt_base_id="author_facing_editorial_copilot",
        prompt_base_version="v1",
        prompt_template_id="editorial_revision",
        prompt_template_version="v1",
        semantic_flow_name="editorial_revision",
        semantic_response_kind="revision_guidance",
        model_profile_used="openai_chatgpt",
        base_template_sections={"objective": "Test prompt"},
        dynamic_context_payload={
            "allow_live_provider": allow_live_provider,
            "exact_artifact_resolution": True,
            "semantic_working_sufficiency": ready,
            "resolved_target": {"target_type": "scene", "target_id": "scene_12"},
            "candidate_targets": [],
            "vault_context_snippets": [],
            "supporting_canon": [],
            "preserve_constraints": ["preserve_scene_conflict"],
            "change_signals": ["clarity_issue"],
        },
        trace_rendered_prompt_payload={
            "system_prompt": "Test system prompt",
            "user_payload": {
                "allow_live_provider": allow_live_provider,
                "exact_artifact_resolution": True,
                "semantic_working_sufficiency": ready,
                "resolved_target": {"target_type": "scene", "target_id": "scene_12"},
                "candidate_targets": [],
                "vault_context_snippets": [],
                "supporting_canon": [],
                "preserve_constraints": ["preserve_scene_conflict"],
                "change_signals": ["clarity_issue"],
            },
            "prompt_sections": [{"name": "objective", "value": "Test prompt"}],
            "output_wrapper": "json_payload",
            "explicitness": "balanced",
        },
        llm_rendered_prompt_payload={
            "system_prompt": "Test system prompt",
            "user_payload": {
                "flow_goal": "Help the author revise with precision while preserving voice and dynamics.",
                "best_candidate_targets": [{"target_type": "scene", "target_id": "scene_12"}],
                "preserve_constraints": ["preserve_scene_conflict"],
                "anchored_context_summary": [],
                "supporting_canon_summary": [],
                "clarification_need": {"required": not ready},
            },
            "output_wrapper": "json_payload",
            "explicitness": "balanced",
        },
        anchored_evidence_used={"resolved_target": {"target_type": "scene", "target_id": "scene_12"}},
        response_support_summary={"resolved_target": {"target_type": "scene", "target_id": "scene_12"}},
        response_generation_ready=ready,
    )


if __name__ == "__main__":
    unittest.main()
