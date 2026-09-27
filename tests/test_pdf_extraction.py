import tempfile
import unittest
from pathlib import Path

import pymupdf

from app.pdf_extraction import extract_pdf, extract_text_layout


class PdfExtractionTests(unittest.TestCase):
    def test_text_page_keeps_heading_and_table_rows(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rules.pdf"
            pdf = pymupdf.open()
            page = pdf.new_page()
            page.insert_text((72, 72), "6-2 R-2 Residential", fontsize=14)
            rows = [("Use", "Limit"), ("Guest house", "900 square feet")]
            for row, (left, right) in enumerate(rows):
                y = 130 + row * 30
                page.insert_text((80, y), left)
                page.insert_text((290, y), right)
            for x in (72, 280, 470):
                page.draw_line((x, 106), (x, 180), color=(0, 0, 0))
            for y in (106, 145, 180):
                page.draw_line((72, y), (470, y), color=(0, 0, 0))
            pdf.save(path)
            pdf.close()

            pages = extract_pdf(path)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].metadata["extraction_method"], "text")
        self.assertIn("6-2 R-2 Residential", pages[0].page_content)
        self.assertIn("| Guest house | 900 square feet |", pages[0].page_content)

    def test_scanned_page_uses_ocr_and_blank_page_is_flagged(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "scans.pdf"
            source = pymupdf.open()
            page = source.new_page(width=900, height=400)
            page.insert_text((40, 90), "Guest houses in R-2 are limited to 900 square feet.", fontsize=23)
            image = page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
            source.close()
            pdf = pymupdf.open()
            scan = pdf.new_page(width=900, height=400)
            scan.insert_image(scan.rect, stream=image)
            pdf.new_page()
            pdf.save(path)
            pdf.close()

            pages = extract_pdf(path)

        self.assertEqual(pages[0].metadata["extraction_method"], "ocr")
        self.assertIn("900 square feet", pages[0].page_content)
        self.assertFalse(pages[0].metadata["low_text"])
        self.assertTrue(pages[1].metadata["low_text"])
        self.assertIn("little or no text", pages[1].metadata["extraction_warning"])

    def test_empty_page_is_flagged_without_running_ocr(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "empty.pdf"
            pdf = pymupdf.open()
            pdf.new_page()
            pdf.save(path)
            pdf.close()
            pages = extract_pdf(path, ocr=lambda image: self.fail("OCR should not run on an empty page"))
        self.assertTrue(pages[0].metadata["low_text"])

    def test_unruled_table_keeps_row_and_column_association(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "unruled.pdf"
            pdf = pymupdf.open()
            page = pdf.new_page()
            page.insert_text((72, 72), "6-2 R-2 Residential", fontsize=14)
            for y, left, right in [
                (130, "Use", "Limit"),
                (160, "Guest house", "900 square feet"),
                (190, "Shed", "500 square feet"),
            ]:
                page.insert_text((80, y), left)
                page.insert_text((290, y), right)
            pdf.save(path)
            pdf.close()
            pages = extract_pdf(path)
        self.assertIn("| Guest house | 900 square feet |", pages[0].page_content)

    def test_paragraph_columns_do_not_break_a_rule_sentence(self):
        path = Path(__file__).resolve().parents[1] / "data" / "zoning-ordinance-082024-rev.pdf"
        with pymupdf.open(path) as pdf:
            text = extract_text_layout(pdf[53])
        self.assertIn("Said guesthouse shall be limited to 900 square feet.", text)


if __name__ == "__main__":
    unittest.main()
