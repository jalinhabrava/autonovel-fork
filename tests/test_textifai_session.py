import tempfile
import unittest
from pathlib import Path

from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault


class TextifAISessionTests(unittest.TestCase):
    def test_create_session_from_runtime_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                        "AUTONOVEL_WRITER_MODEL=llama3.2",
                    ]
                )
                + "\n"
            )

            session = create_session(load_runtime_environment(base_dir))

            self.assertEqual(session.backend, "vault")
            self.assertEqual(session.provider, "ollama")
            self.assertEqual(session.writer_model, "llama3.2")
            self.assertEqual(session.locale, "en")
            self.assertEqual(session.mode, "normal")
            self.assertEqual(session.policy_name, "default")
            self.assertEqual(session.token_budget, 4000)


if __name__ == "__main__":
    unittest.main()
