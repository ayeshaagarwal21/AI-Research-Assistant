"""Answer the questions that are *written inside* the user's PDFs
(exam papers, assignments, quizzes, worksheets...).

Normal document Q&A searches for a few matching chunks. That doesn't work for
"answer question 5" or "solve everything", because the request doesn't resemble the
text. So here the model reads the actual pages (all of them, or the ones the user
names) and answers the questions it finds there.
"""
import re
from typing import List, Optional, Tuple

MAX_DOC_CHARS = 300_000  # ~75k tokens - fine for Gemini, and keeps latency/cost sane

_SOLVE_VERBS = re.compile(
    r"\b(answer|answers|answering|solve|solving|solution|solutions|attempt|work out)\b",
    re.IGNORECASE,
)
_QUESTION_WORDS = re.compile(
    r"\b(questions?|qns?|ques|exercises?|problems?|mcqs?|quiz|worksheet|assignment)\b"
    r"|\bq\s*\.?\s*\d+\b",
    re.IGNORECASE,
)
_PAGE_RANGE = re.compile(r"\bpages?\s*(\d+)(?:\s*(?:-|–|to)\s*(\d+))?", re.IGNORECASE)

PDF_QUESTIONS_PROMPT = """
You are an AI study assistant. Below is the text of the user's PDF document(s).
Each page starts with a marker like "--- file.pdf, page 2 ---".
The PDF(s) contain questions (for example an exam paper, assignment, quiz or worksheet).

The user's request:
{question}

Instructions:
1. Find the questions in the document that the user is asking about. If they ask for
   "all" questions, or don't specify, answer every question you find. If they name a
   question number or page, answer only those.
2. For each question: write its number and a short version of the question, then the
   answer. Show the key steps for calculations or reasoning. For multiple-choice
   questions, state the correct option and give one line of explanation.
3. Use information from the document when a question depends on it (a passage, table
   or case study). Otherwise answer from your own knowledge.
4. Mention where each question is, like (file.pdf, p. 2).
5. Never invent questions that are not in the document. If you cannot find what the
   user asked for, say so.
6. If a question is cut off or unreadable (for example it depends on a diagram you
   cannot see), say so instead of guessing.

Earlier conversation:
{chat_history}

Document text:
{document}
"""


def wants_pdf_questions(text: str) -> bool:
    """Does this message ask to answer/solve questions (so we should read the PDF itself)?"""
    return bool(_SOLVE_VERBS.search(text) and _QUESTION_WORDS.search(text))


def select_pages(pages: List[dict], request: str) -> List[dict]:
    """Narrow down to the files / page range the user mentioned (else keep everything)."""
    lowered = request.lower()

    sources = []
    for page in pages:
        if page["source"] not in sources:
            sources.append(page["source"])

    named = []
    for source in sources:
        stem = re.sub(r"\.pdf$", "", source, flags=re.IGNORECASE).lower()
        by_full_name = source.lower() in lowered
        # Short stems like "a" would match ordinary words, so require 5+ characters.
        by_stem = len(stem) >= 5 and re.search(r"\b" + re.escape(stem) + r"\b", lowered)
        if by_full_name or by_stem:
            named.append(source)

    selected = [p for p in pages if p["source"] in named] if named else list(pages)

    match = _PAGE_RANGE.search(request)
    if match:
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start > end:
            start, end = end, start
        selected = [p for p in selected if start <= p["page"] <= end]
    return selected


def build_document_text(pages: List[dict], max_chars: int = MAX_DOC_CHARS) -> Tuple[str, int]:
    """Join pages with markers. Returns (text, number_of_pages_included)."""
    parts, total, used = [], 0, 0
    for page in pages:
        block = f"--- {page['source']}, page {page['page']} ---\n{page['text'].strip()}\n"
        remaining = max_chars - total
        if len(block) > remaining:
            if not parts:  # a single enormous page: keep the part that fits
                parts.append(block[:remaining])
                used = 1
            break
        parts.append(block)
        total += len(block)
        used += 1
    return "\n".join(parts), used


def build_prompt(question: str, document: str, history: Optional[List[dict]] = None) -> str:
    history_text = (
        "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)
        if history
        else "(none)"
    )
    return PDF_QUESTIONS_PROMPT.format(
        question=question.strip(), chat_history=history_text, document=document
    )


def answer_pdf_questions(
    question: str, pages: List[dict], history: Optional[List[dict]] = None
) -> str:
    selected = select_pages(pages, question)
    if not selected:
        return "I couldn't find those pages or files in your uploaded documents."

    document, used = build_document_text(selected)

    # Imported here so the helpers above are usable (and testable) without langchain.
    from backend.app.services.llm_service import get_llm
    from backend.app.services.rag_service import _as_text

    answer = _as_text(get_llm().invoke(build_prompt(question, document, history)).content).strip()

    if used < len(selected):
        answer += (
            f"\n\n_Note: the document is long, so only the first {used} of {len(selected)} "
            "pages were read. Ask for a page range (for example "
            '"answer the questions on pages 20-25") to cover the rest._'
        )
    return answer
