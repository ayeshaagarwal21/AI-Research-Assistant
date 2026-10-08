import unittest

from backend.app.services.pdf_question_service import (
    build_document_text,
    build_prompt,
    select_pages,
    wants_pdf_questions,
)

PAGES = [
    {"source": "exam.pdf", "page": 1, "text": "Q1. What is 2+2?"},
    {"source": "exam.pdf", "page": 2, "text": "Q2. Define AI."},
    {"source": "exam.pdf", "page": 3, "text": "Q3. Name a sorting algorithm."},
    {"source": "notes.pdf", "page": 1, "text": "Chapter one."},
    {"source": "a.pdf", "page": 1, "text": "Tiny file."},
]


class IntentTests(unittest.TestCase):
    def test_requests_to_solve_questions_are_detected(self):
        for text in [
            "answer all the questions in the pdf",
            "Solve question 3",
            "Answer Q5",
            "what is the answer to question 2?",
            "questions ka answer do",
            "give me the solutions to the assignment",
            "attempt the MCQs on page 2",
        ]:
            self.assertTrue(wants_pdf_questions(text), text)

    def test_normal_questions_are_not_detected(self):
        for text in [
            "summarize the pdf",
            "what are the main findings?",
            "how many questions are there?",
            "list the questions",
            "answer this: what is machine learning?",
            "explain machine learning",
        ]:
            self.assertFalse(wants_pdf_questions(text), text)


class SelectPagesTests(unittest.TestCase):
    def test_no_hints_keeps_everything(self):
        self.assertEqual(len(select_pages(PAGES, "answer all the questions")), 5)

    def test_single_page(self):
        result = select_pages(PAGES, "answer the questions on page 2")
        self.assertEqual([(p["source"], p["page"]) for p in result], [("exam.pdf", 2)])

    def test_page_range_and_file_name(self):
        result = select_pages(PAGES, "solve questions on pages 1-2 of exam.pdf")
        self.assertEqual([p["page"] for p in result], [1, 2])
        self.assertTrue(all(p["source"] == "exam.pdf" for p in result))

    def test_reversed_range(self):
        self.assertEqual(len(select_pages(PAGES, "answer questions pages 3 to 2 exam.pdf")), 2)

    def test_file_mentioned_without_extension(self):
        result = select_pages(PAGES, "answer the questions in notes")
        self.assertEqual([p["source"] for p in result], ["notes.pdf"])

    def test_short_file_names_do_not_match_ordinary_words(self):
        # "a.pdf" has the stem "a", which appears in this sentence as a normal word.
        self.assertEqual(len(select_pages(PAGES, "answer a question please")), 5)

    def test_page_that_does_not_exist(self):
        self.assertEqual(select_pages(PAGES, "answer the questions on page 99"), [])


class DocumentTextTests(unittest.TestCase):
    def test_pages_get_markers(self):
        text, used = build_document_text(PAGES[:2])
        self.assertEqual(used, 2)
        self.assertIn("--- exam.pdf, page 1 ---", text)
        self.assertIn("Q2. Define AI.", text)

    def test_long_documents_are_cut_at_a_page_boundary(self):
        text, used = build_document_text(PAGES, max_chars=100)
        self.assertLess(used, len(PAGES))
        self.assertLessEqual(len(text), 100)

    def test_single_huge_page_is_truncated_not_dropped(self):
        big = [{"source": "x.pdf", "page": 1, "text": "word " * 1000}]
        text, used = build_document_text(big, max_chars=200)
        self.assertEqual(used, 1)
        self.assertEqual(len(text), 200)


class PromptTests(unittest.TestCase):
    def test_prompt_contains_request_document_and_history(self):
        prompt = build_prompt("answer Q1", "--- doc ---\n{braces} are fine",
                              [{"role": "user", "content": "hi"}])
        self.assertIn("answer Q1", prompt)
        self.assertIn("{braces} are fine", prompt)
        self.assertIn("User: hi", prompt)

    def test_no_history(self):
        self.assertIn("(none)", build_prompt("q", "doc"))


if __name__ == "__main__":
    unittest.main()
