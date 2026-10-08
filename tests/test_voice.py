import unittest

from backend.app.services.voice_service import clean_for_speech, text_to_mp3


class VoiceTests(unittest.TestCase):
    def test_removes_citations_and_markdown(self):
        text = "**ML** is great (paper.pdf, p. 3)."
        self.assertEqual(clean_for_speech(text), "ML is great .")

    def test_removes_page_citation_variants(self):
        self.assertEqual(clean_for_speech("Yes (My Notes.PDF, p 12) really"), "Yes really")

    def test_long_text_is_truncated(self):
        self.assertEqual(len(clean_for_speech("word " * 1000)), 1500)

    def test_nothing_to_read_raises(self):
        with self.assertRaises(ValueError):
            text_to_mp3("***")


if __name__ == "__main__":
    unittest.main()
