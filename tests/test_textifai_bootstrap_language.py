import unittest

from textifai.bootstrap.language import detect_language_profile


class TextifAIBootstrapLanguageTests(unittest.TestCase):
    def test_detect_language_profile_handles_en_es_ja(self):
        english = detect_language_profile("The room was silent and the client waited.")
        spanish = detect_language_profile("La reunión empezó en silencio y el cliente observó.")
        japanese = detect_language_profile("これは会議の記録です。静かに始まった。")

        self.assertIn("en", english.detected_languages)
        self.assertIn("es", spanish.detected_languages)
        self.assertIn("ja", japanese.detected_languages)


if __name__ == "__main__":
    unittest.main()
