import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from textifai.router import dispatch_command
from vault.bootstrap import bootstrap_vault


class TextifAIAdvancedShellTests(unittest.TestCase):
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

    def test_policy_and_budget_commands_work_in_session(self):
        response = dispatch_command(self.session, "policy")
        self.assertIn("active_policy", response)
        self.assertIn("default", response)

        response = dispatch_command(self.session, "policy strict_canon")
        self.assertEqual(self.session.policy_name, "strict_canon")
        self.assertIn("Policy set to strict_canon", response)

        response = dispatch_command(self.session, "budget")
        self.assertIn("4000", response)

        response = dispatch_command(self.session, "budget 2500")
        self.assertEqual(self.session.token_budget, 2500)
        self.assertIn("2500", response)

    def test_request_and_pack_use_last_context(self):
        with patch("textifai.router.build_world_context", return_value=_pack("world")):
            dispatch_command(self.session, "world")

        request_response = dispatch_command(self.session, "request")
        self.assertIn("context request", request_response.lower())
        self.assertIn("world_lookup", request_response)

        pack_response = dispatch_command(self.session, "pack")
        self.assertIn("context pack", pack_response.lower())
        self.assertIn("hard_constraints", pack_response)

    def test_context_debug_is_gated_by_mode_and_uses_last_request(self):
        with patch("textifai.router.build_world_context", return_value=_pack("world")):
            dispatch_command(self.session, "world")

        blocked = dispatch_command(self.session, "context-debug")
        self.assertIn("advanced mode", blocked.lower())

        self.session.mode = "advanced"
        with patch("textifai.router.debug_context", return_value=_debug_result("world")) as debug_mock:
            response = dispatch_command(self.session, "context-debug")
        debug_mock.assert_called_once()
        self.assertIn("context debug", response.lower())
        self.assertIsNotNone(self.session.last_context_debug)


def _pack(target: str) -> dict:
    return {
        "type": "context_pack",
        "intent": "world_lookup",
        "scope": {"target_id": target},
        "policy": {"name": "default"},
        "hard_constraints": [{"title": "Magic Costs"}],
        "narrative_context": [{"title": "Local Scene"}],
        "voice_context": {"project_voice": [], "character_voice": []},
        "evidence": [{"title": "Chapter 1"}],
        "meta": {},
    }


def _debug_result(target: str) -> dict:
    return {
        "request": {
            "intent": "world_lookup",
            "target_id": target,
            "target_type": "project",
            "narrative_scope": "project",
            "retrieval_scope": ["canon", "lore"],
            "token_budget": 4000,
            "policy_name": "default",
        },
        "resolved_intent": {"name": "world_lookup"},
        "resolved_scope": {"narrative_scope": "project"},
        "policy": {"name": "default"},
        "candidates": [
            {
                "id": "magic_costs",
                "final_section": "hard_constraints",
                "score": {"total": 2.5},
            }
        ],
        "context_pack": _pack(target),
    }


if __name__ == "__main__":
    unittest.main()
