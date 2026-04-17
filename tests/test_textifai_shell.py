import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from textifai.shell import handle_command, run_shell
from vault.bootstrap import bootstrap_vault


class TextifAIShellTests(unittest.TestCase):
    def test_handle_command_supports_help_status_mode_and_exit(self):
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
            session = create_session(load_runtime_environment(base_dir))

            self.assertIn("Available commands", handle_command(session, "help"))
            self.assertIn("TextifAI session status", handle_command(session, "status"))
            self.assertIn("world", handle_command(session, "help"))
            self.assertIn("bootstrap voice", handle_command(session, "help"))
            self.assertIn("Current mode: normal", handle_command(session, "mode"))
            self.assertIn("Mode set to advanced", handle_command(session, "mode advanced"))
            self.assertEqual(session.mode, "advanced")
            self.assertIn("Leaving TextifAI", handle_command(session, "quit"))
            self.assertFalse(session.running)

    def test_run_shell_processes_basic_command_sequence(self):
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
            session = create_session(load_runtime_environment(base_dir))
            commands = iter(["status", "mode advanced", "exit"])
            outputs: list[str] = []

            code = run_shell(
                session,
                input_fn=lambda _: next(commands),
                output_fn=outputs.append,
            )

            self.assertEqual(code, 0)
            joined = "\n".join(outputs)
            self.assertIn("TextifAI terminal runtime", joined)
            self.assertIn("TextifAI session status", joined)
            self.assertIn("Mode set to advanced", joined)

    def test_handle_command_routes_domain_commands(self):
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
            session = create_session(load_runtime_environment(base_dir))

            with unittest.mock.patch(
                "textifai.shell.dispatch_command",
                return_value="TextifAI context result\n- target: world",
            ) as router_mock:
                response = handle_command(session, "world")

            router_mock.assert_called_once()
            self.assertIn("context result", response.lower())


if __name__ == "__main__":
    unittest.main()
