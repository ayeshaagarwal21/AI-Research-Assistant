import io
import unittest

from utils.pdf_reader import PDFReadError, extract_pdf_pages


def make_pdf(text=None) -> bytes:
    """Build a minimal one-page PDF by hand (no extra libraries needed)."""
    stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET" if text else ""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF"
    ).encode()
    return out


class PDFReaderTests(unittest.TestCase):
    def test_extracts_text_with_source_and_page(self):
        pages = extract_pdf_pages(io.BytesIO(make_pdf("Hello research world")), "paper.pdf")
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["source"], "paper.pdf")
        self.assertEqual(pages[0]["page"], 1)
        self.assertIn("Hello research world", pages[0]["text"])

    def test_pdf_without_text_is_reported(self):
        with self.assertRaises(PDFReadError) as ctx:
            extract_pdf_pages(io.BytesIO(make_pdf(None)), "scan.pdf")
        self.assertIn("No extractable text", str(ctx.exception))

    def test_garbage_file_is_reported_not_crashing(self):
        with self.assertRaises(PDFReadError):
            extract_pdf_pages(io.BytesIO(b"this is not a pdf"), "fake.pdf")


if __name__ == "__main__":
    unittest.main()
