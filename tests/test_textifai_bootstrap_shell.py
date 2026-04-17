import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from textifai.router import dispatch_command
from vault.bootstrap import bootstrap_vault


class TextifAIBootstrapShellTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tempdir.name)
        self.vault_root = self.base_dir / "Vault"
        bootstrap_vault(self.vault_root, title="Test Project")
        (self.base_dir / ".env").write_text(
            "\n".join(
                [
                    "AUTONOVEL_PROJECT_BACKEND=vault",
                    f"AUTONOVEL_VAULT_ROOT={self.vault_root}",
                    "AUTONOVEL_TEXT_PROVIDER=ollama",
                ]
            )
            + "\n"
        )
        self.session = create_session(load_runtime_environment(self.base_dir))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_bootstrap_without_subtype_can_cancel(self):
        prompts = iter(["cancel"])
        response = dispatch_command(self.session, "bootstrap", input_fn=lambda _: next(prompts))
        self.assertEqual(response, "Bootstrap cancelled.")

    def test_bootstrap_voice_uses_existing_extractor(self):
        prompts = iter(["ch_01,ch_02"])
        with patch(
            "textifai.router.extract_voice",
            return_value={"status": "written", "target_id": "voice", "target_type": "voice", "state": "pending_revision"},
        ) as voice_mock:
            response = dispatch_command(self.session, "bootstrap voice", input_fn=lambda _: next(prompts))
        voice_mock.assert_called_once()
        self.assertIn("bootstrap result", response.lower())
        self.assertIn("written: 1", response.lower())

    def test_bootstrap_selector_routes_to_characters(self):
        prompts = iter(["characters", "ch_03", "", ""])
        with patch(
            "textifai.router.extract_characters",
            return_value=[
                {"status": "written", "target_id": "sera", "target_type": "character", "state": "pending_revision"},
                {"status": "written", "target_id": "ren", "target_type": "character", "state": "proposed"},
            ],
        ) as characters_mock:
            response = dispatch_command(self.session, "bootstrap", input_fn=lambda _: next(prompts))
        characters_mock.assert_called_once()
        self.assertIn("type: characters", response.lower())
        self.assertIn("written: 2", response.lower())

    def test_bootstrap_canon_and_timeline_render_notes(self):
        with patch(
            "textifai.router.extract_canon",
            return_value=[{"status": "written", "target_id": "magic_costs", "target_type": "decision", "state": "proposed"}],
        ):
            canon_response = dispatch_command(self.session, "bootstrap canon ch_01")
        self.assertIn("extracted proposals", canon_response.lower())

        with patch(
            "textifai.router.extract_timeline",
            return_value=[{"status": "written", "target_id": "timeline_ch_01", "target_type": "lore", "state": "proposed"}],
        ):
            timeline_response = dispatch_command(self.session, "bootstrap timeline ch_01")
        self.assertIn("provisional lore notes", timeline_response.lower())


if __name__ == "__main__":
    unittest.main()
