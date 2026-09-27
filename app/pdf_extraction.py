"""Page-level PDF extraction with OCR fallback and layout-aware table output."""

import re
from bisect import bisect_right
from pathlib import Path

import pymupdf
from langchain_core.documents import Document
from rapidocr import RapidOCR

MIN_TEXT_CHARS = 40
MIN_USABLE_CHARS = 30


def meaningful_chars(text: str) -> int:
    return sum(character.isalnum() for character in text)


def text_is_usable(text: str) -> bool:
    words = re.findall(r"\b\w{2,}\b", text)
    return meaningful_chars(text) >= MIN_TEXT_CHARS and len(words) >= 5 and "\ufffd" not in text


def table_markdown(rows: list[list[str | None]]) -> str:
    lines = []
    for row in rows:
        cells = [" ".join((cell or "").split()).replace("|", "\\|") for cell in row]
        if any(cells):
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def useful_table(table) -> bool:
    """Reject sparse whole-page grids inferred from ordinary paragraph spacing."""
    rows = table.extract()
    filled = sum(bool((cell or "").strip()) for row in rows for cell in row)
    density = filled / max(1, table.row_count * table.col_count)
    return table.row_count >= 2 and table.col_count >= 2 and (
        (table.col_count <= 4 and density >= 0.5) or density >= 0.7
    )


def text_table_rows(page: pymupdf.Page, table) -> list[list[str]]:
    """Recover full cells where text-based table detection clips the final column."""
    words = page.get_text("words")
    bounds = [row.bbox for row in table.rows]
    row_tops = [bound[1] for bound in bounds]
    column_starts = [[cell[0] for cell in row.cells] for row in table.rows]
    cells = [[[] for _ in starts] for starts in column_starts]
    left = table.bbox[0]
    for word in words:
        x = (word[0] + word[2]) / 2
        if x < left:
            continue
        y = (word[1] + word[3]) / 2
        row_number = bisect_right(row_tops, y) - 1
        if row_number < 0 or y >= bounds[row_number][3]:
            continue
        column = max(0, bisect_right(column_starts[row_number], x) - 1)
        cells[row_number][column].append(word)
    return [
        [" ".join(word[4] for word in sorted(cell, key=lambda item: item[0])) for cell in row]
        for row in cells
    ]


def extract_text_layout(page: pymupdf.Page) -> str:
    blocks = [block for block in page.get_text("blocks", sort=True) if len(block) >= 7 and block[6] == 0 and block[4].strip()]
    if not blocks:
        return ""
    tables = []
    text_tables = False
    try:
        tables = [table for table in page.find_tables().tables if useful_table(table)]
        if not tables:
            # Text alignment can reveal tables that have no drawn cell borders.
            tables = [
                table for table in page.find_tables(strategy="text").tables
                if useful_table(table)
            ]
            text_tables = True
    except (ValueError, RuntimeError):
        pass
    regions = [pymupdf.Rect(table.bbox) for table in tables]
    items = []
    for block in blocks:
        rect = pymupdf.Rect(block[:4])
        if any((rect & region).get_area() / max(rect.get_area(), 1) > 0.5 for region in regions):
            continue
        content = block[4].strip()
        if content:
            items.append((rect.y0, rect.x0, content))
    for table in tables:
        content = table_markdown(text_table_rows(page, table) if text_tables else table.extract())
        if content:
            items.append((table.bbox[1], table.bbox[0], content))
    items.sort(key=lambda item: (item[0], item[1]))
    text = "\n\n".join(content for _, _, content in items)
    # PDF text layers often put a section number and its title on separate lines.
    return re.sub(
        r"(?m)^([ \t]*\d{1,3}-\d+(?:\.\d+)?\.?)[ \t]*\n[ \t]*([A-Z][^\n]*)",
        r"\1 \2",
        text,
    )


def extract_pdf(path: str | Path, ocr=None) -> list[Document]:
    """Use native text on good pages and OCR on scanned or weak pages."""
    path = Path(path)
    pages = []
    engine = ocr
    with pymupdf.open(path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            native = extract_text_layout(page)
            content = native
            method = "text"
            ocr_chars = 0
            # A genuinely empty PDF page has nothing that OCR could recover.
            if not text_is_usable(native) and (native.strip() or page.get_images() or page.get_drawings()):
                if engine is None:
                    engine = RapidOCR()
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                recognized = engine(pixmap.tobytes("png"))
                ocr_text = recognized.to_markdown().strip() if recognized and len(recognized) else ""
                ocr_chars = meaningful_chars(ocr_text)
                if ocr_chars > meaningful_chars(native):
                    content = ocr_text
                    method = "ocr"
            chars = meaningful_chars(content)
            low_text = chars < MIN_USABLE_CHARS
            pages.append(Document(
                page_content=content,
                metadata={
                    "source": path.name,
                    "page": page_number,
                    "extraction_method": method,
                    "text_chars": chars,
                    "ocr_chars": ocr_chars,
                    "low_text": low_text,
                    "extraction_warning": "Page has little or no text after extraction and OCR." if low_text else "",
                },
            ))
    return pages
