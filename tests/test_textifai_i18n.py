import os
import tempfile
import unittest
from pathlib import Path

from textifai.i18n import get_translator
from textifai.runtime_config import load_runtime_environment


class TextifAII18nTests(unittest.TestCase):
    def test_runtime_environment_uses_explicit_locale_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            (base_dir / ".env").write_text("TEXTIFAI_LOCALE=es\n")
            env = load_runtime_environment(base_dir)
            self.assertEqual(env.locale, "es")

    def test_runtime_environment_falls_back_to_detected_or_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            old_lang = os.environ.get("LANG")
            try:
                os.environ["LANG"] = "es_ES.UTF-8"
                env = load_runtime_environment(base_dir)
                self.assertEqual(env.locale, "es")
            finally:
                if old_lang is None:
                    os.environ.pop("LANG", None)
                else:
                    os.environ["LANG"] = old_lang

    def test_translator_falls_back_to_english_key(self):
        translator = get_translator("es")
        text = translator.t("doctor.next_step.ready")
        self.assertTrue(text)
        self.assertNotIn("[missing:", text)
