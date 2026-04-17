import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from textifai.cli import main
from vault.bootstrap import bootstrap_vault


class TextifAICliTests(unittest.TestCase):
    def test_chat_uses_existing_runtime_environment(self):
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
                    ]
                )
                + "\n"
            )

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["chat", "--base-dir", str(base_dir)])

            output = buffer.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("TextifAI product runtime", output)
            self.assertIn("Vault:", output)


if __name__ == "__main__":
    unittest.main()
