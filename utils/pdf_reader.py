"""PDF text extraction that keeps track of file name and page number."""
from typing import List

from pypdf import PdfReader


class PDFReadError(Exception):
    """Raised when a PDF cannot be turned into usable text."""


def extract_pdf_pages(file_obj, filename: str) -> List[dict]:
    """Return [{'source': filename, 'page': 1, 'text': '...'}, ...] (pages are 1-based).

    `file_obj` is any binary file-like object (e.g. FastAPI's UploadFile.file).
    Pages without extractable text are skipped.
    """
    try:
        file_obj.seek(0)
        reader = PdfReader(file_obj)

        if reader.is_encrypted and not reader.decrypt(""):
            raise PDFReadError("The PDF is password-protected")

        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append({"source": filename, "page": number, "text": text})
    except PDFReadError:
        raise
    except Exception as exc:  # pypdf raises several different errors for bad files
        raise PDFReadError(f"Could not read the PDF ({exc})") from exc

    if not pages:
        raise PDFReadError(
            "No extractable text found (it may be a scanned/image-only PDF)"
        )
    return pages
