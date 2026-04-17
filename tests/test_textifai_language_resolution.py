import unittest

from textifai.language_policy import LanguagePolicy
from textifai.language_resolution import resolve_language_for_operation


class TextifAILanguageResolutionTests(unittest.TestCase):
    def setUp(self):
        self.policy = LanguagePolicy(
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="en",
            mixed_language_allowed=True,
            artifact_languages={
                "chapter": "ja",
                "scene": "ja",
                "decision": "es",
                "lore": "es",
                "voice": "ja",
            },
        )

    def test_user_origin_prefers_user_command_then_interface(self):
        resolution = resolve_language_for_operation(
            self.policy,
            artifact_type="chapter",
            operation_origin="user",
        )
        self.assertEqual(resolution.operation_language, "es")
        self.assertEqual(resolution.artifact_target_language, "ja")

    def test_user_origin_can_fall_back_to_interface_language(self):
        policy = LanguagePolicy(
            interface_language="es",
            user_command_language="",
            internal_system_language="en",
            project_default_language="en",
            mixed_language_allowed=True,
            artifact_languages={"decision": "es"},
        )
        resolution = resolve_language_for_operation(
            policy,
            artifact_type="decision",
            operation_origin="user",
        )
        self.assertEqual(resolution.operation_language, "es")
        self.assertEqual(resolution.artifact_target_language, "es")

    def test_explicit_artifact_language_overrides_policy(self):
        resolution = resolve_language_for_operation(
            self.policy,
            artifact_type="chapter",
            operation_origin="user",
            explicit_artifact_language="fr",
        )
        self.assertEqual(resolution.artifact_target_language, "fr")

    def test_internal_origin_uses_internal_system_language(self):
        resolution = resolve_language_for_operation(
            self.policy,
            artifact_type="lore",
            operation_origin="system",
        )
        self.assertEqual(resolution.operation_language, "en")
        self.assertEqual(resolution.artifact_target_language, "es")


if __name__ == "__main__":
    unittest.main()
