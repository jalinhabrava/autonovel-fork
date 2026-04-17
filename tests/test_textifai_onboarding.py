import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.onboarding import run_onboarding


class TextifAIOnboardingTests(unittest.TestCase):
    def test_onboarding_creates_vault_and_updates_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            (base_dir / ".env.example").write_text("AUTONOVEL_TEXT_PROVIDER=anthropic\n")
            responses = iter(
                [
                    "",   # default vault path
                    "",   # create new vault yes
                    "",   # default project title
                    "e",  # empty
                    "ollama",
                    "",   # writer model
                ]
            )

            summary = run_onboarding(
                base_dir=base_dir,
                input_fn=lambda _: next(responses),
                output_fn=lambda _: None,
            )

            vault_path = Path(summary["vault_path"])
            self.assertTrue(vault_path.exists())
            self.assertEqual(summary["provider"], "ollama")
            env_text = (base_dir / ".env").read_text()
            self.assertIn("AUTONOVEL_PROJECT_BACKEND=vault", env_text)
            self.assertIn(f"AUTONOVEL_VAULT_ROOT={vault_path}", env_text)
            self.assertIn("AUTONOVEL_TEXT_PROVIDER=ollama", env_text)


if __name__ == "__main__":
    unittest.main()
