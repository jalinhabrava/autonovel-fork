import tempfile
import unittest
from pathlib import Path

from textifai.doctor import run_doctor
from vault.bootstrap import bootstrap_vault


class TextifAIDoctorTests(unittest.TestCase):
    def test_doctor_reports_ok_for_valid_vault_runtime(self):
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

            report = run_doctor(base_dir=base_dir)

            self.assertEqual(report["overall"], "ok")
            self.assertTrue(any(check["name"] == "vault" and check["status"] == "ok" for check in report["checks"]))


if __name__ == "__main__":
    unittest.main()
