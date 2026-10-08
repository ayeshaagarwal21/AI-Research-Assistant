import unittest

from backend.app.services.vision_service import build_prompt, detect_image_type


class DetectImageTypeTests(unittest.TestCase):
    def test_recognises_formats_by_content(self):
        self.assertEqual(detect_image_type(b"\x89PNG\r\n\x1a\n" + b"0" * 20), "image/png")
        self.assertEqual(detect_image_type(b"\xff\xd8\xff\xe0" + b"0" * 20), "image/jpeg")
        self.assertEqual(detect_image_type(b"GIF89a" + b"0" * 20), "image/gif")
        self.assertEqual(detect_image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "image/webp")

    def test_rejects_non_images(self):
        self.assertIsNone(detect_image_type(b"%PDF-1.4 not an image"))
        self.assertIsNone(detect_image_type(b"hello world"))
        self.assertIsNone(detect_image_type(b""))


class BuildPromptTests(unittest.TestCase):
    def test_default_note_when_user_wrote_nothing(self):
        prompt = build_prompt("")
        self.assertIn("answer the question(s) in the image", prompt)
        self.assertIn("(none)", prompt)  # no history

    def test_includes_instruction_and_history(self):
        prompt = build_prompt("only question 2", [{"role": "user", "content": "hi"}])
        self.assertIn("only question 2", prompt)
        self.assertIn("User: hi", prompt)


if __name__ == "__main__":
    unittest.main()
