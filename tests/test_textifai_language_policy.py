import json
import tempfile
import unittest
from pathlib import Path

from textifai.language_policy import SUPPORTED_ARTIFACT_LANGUAGE_TYPES, artifact_language, load_language_policy
from textifai.runtime_config import load_runtime_environment


class TextifAILanguagePolicyTests(unittest.TestCase):
    def test_language_policy_uses_env_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            (base_dir / "config").mkdir()
            (base_dir / "config" / "language_policy.json").write_text(
                json.dumps(
                    {
                        "interface_language": "en",
                        "user_command_language": "en",
                        "internal_system_language": "en",
                        "project_default_language": "en",
                        "mixed_language_allowed": True,
                        "artifact_languages": {"chapter": "en", "canon": "es"},
                    }
                )
            )
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "TEXTIFAI_INTERFACE_LANGUAGE=es",
                        "TEXTIFAI_USER_COMMAND_LANGUAGE=es",
                        "TEXTIFAI_PROJECT_DEFAULT_LANGUAGE=ja",
                        'TEXTIFAI_ARTIFACT_LANGUAGES={"chapter":"ja","scene":"ja","canon":"es"}',
                    ]
                )
                + "\n"
            )

            env = load_runtime_environment(base_dir)
            policy = env.language_policy

            self.assertEqual(policy.interface_language, "es")
            self.assertEqual(policy.user_command_language, "es")
            self.assertEqual(policy.internal_system_language, "en")
            self.assertEqual(policy.project_default_language, "ja")
            self.assertTrue(policy.mixed_language_allowed)
            self.assertEqual(artifact_language(policy, "chapter"), "ja")
            self.assertEqual(artifact_language(policy, "canon"), "es")
            self.assertEqual(artifact_language(policy, "voice"), "ja")

    def test_project_override_beats_env_for_project_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            (base_dir / "config").mkdir()
            (base_dir / "config" / "language_policy.json").write_text(
                json.dumps(
                    {
                        "interface_language": "en",
                        "user_command_language": "en",
                        "internal_system_language": "en",
                        "project_default_language": "en",
                        "mixed_language_allowed": True,
                        "artifact_languages": {},
                    }
                )
            )
            policy = load_language_policy(
                base_dir,
                env_values={"TEXTIFAI_PROJECT_DEFAULT_LANGUAGE": "es"},
                project_overrides={"project_default_language": "ja", "artifact_languages": {"chapter": "ja"}},
            )
            self.assertEqual(policy.project_default_language, "ja")
            self.assertEqual(artifact_language(policy, "chapter"), "ja")

    def test_artifact_languages_cover_real_system_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            (base_dir / "config").mkdir()
            (base_dir / "config" / "language_policy.json").write_text(
                json.dumps(
                    {
                        "interface_language": "en",
                        "user_command_language": "en",
                        "internal_system_language": "en",
                        "project_default_language": "en",
                        "mixed_language_allowed": True,
                        "artifact_languages": {},
                    }
                )
            )
            policy = load_language_policy(base_dir)
            self.assertTrue(all(key in policy.artifact_languages for key in SUPPORTED_ARTIFACT_LANGUAGE_TYPES))
