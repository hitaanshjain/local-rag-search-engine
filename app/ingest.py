from collections import defaultdict
import json
from hashlib import sha256
from pathlib import Path
import re
from time import sleep
from uuid import uuid4
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.engine import INDEX_VERSION_PATH, PAGE_REPORT_PATH, get_vector_db
from app.pdf_extraction import extract_pdf
from app.provenance import infer_document_provenance

DATA_DIR = "./data"
PAGE_REPORT_NAME = PAGE_REPORT_PATH.name
# "6-15 TCMU Town Center", "Sec. 54-269.  Design Review", or "APPENDIX C". A capital after the
# number rejects cross-references ("54-348 in areas"), and \d{1,3} rejects years ("1995-160").
SECTION_HEADING = re.compile(
    r"(?m)^[ \t]*((?:Sec\.[ \t]*)?\d{1,3}-\d+(?:\.\d+)?\.?[ \t]+[A-Z][^\n]*|APPENDIX[ \t]+[A-Z]\b[^\n]*)"
)


# Charleston page footers ("4-20.1 Supp. No. 6") look like numbered headings.
PAGE_FOOTER = re.compile(r"^\d{1,3}-\d+(?:\.\d+)?\s+Supp\.\s*No\.\s*\d+\s*$")


def section_headings(text):
    return [
        (match.start(), " ".join(match.group(1).split()))
        for match in SECTION_HEADING.finditer(text)
        if ". ." not in match.group(1) and not PAGE_FOOTER.match(match.group(1).strip())
    ]


def assign_sections(chunks):
    """Label each chunk with the section covering most of its text."""
    current_source = None
    current_section = None
    for chunk in chunks:
        if chunk.metadata.get("source") != current_source:
            current_source = chunk.metadata.get("source")
            current_section = None
        text = chunk.page_content
        body_start = text.find("\n") + 1 if text.startswith("Source: ") else 0
        coverage = defaultdict(int)
        position = body_start
        for start, heading in section_headings(text):
            if start < body_start:
                continue
            if current_section:
                coverage[current_section] += start - position
            current_section, position = heading, start
        if current_section:
            coverage[current_section] += len(text) - position
        if coverage:
            chunk.metadata["section"] = max(coverage, key=coverage.get)


def split_section_documents(pages, splitter):
    """Split each page at section headings before applying the size limit."""
    segments = []
    current_source = None
    current_section = None
    for page in pages:
        source = page.metadata.get("source")
        if source != current_source:
            current_source, current_section = source, None
        text = page.page_content
        header, separator, body = text.partition("\n") if text.startswith("Source: ") else ("", "", text)
        headings = section_headings(body)
        boundaries = [(0, current_section)] + [(start, heading) for start, heading in headings]
        pieces = [
            (body[start:end].strip(), section)
            for (start, section), (end, _) in zip(boundaries, boundaries[1:] + [(len(body), None)])
        ]
        # Unreadable pages are reported by page_report, not stored as filler chunks.
        pieces = [(content, section) for content, section in pieces if content]
        for content, section in pieces:
            metadata = dict(page.metadata)
            if section:
                metadata["section"] = section
            else:
                metadata.pop("section", None)
            segments.append(type(page)(page_content=f"{header}{separator}{content}" if header else content, metadata=metadata))
        if headings:
            current_section = headings[-1][1]
    return splitter.split_documents(segments)

def page_report(pages):
    """Per-document page count plus pages that are unreadable or intentionally blank."""
    report = {}
    for page in pages:
        entry = report.setdefault(page.metadata["source"], {"pages": 0, "low_text_pages": [], "blank_pages": []})
        entry["pages"] = max(entry["pages"], page.metadata["page"])
        if page.metadata.get("low_text"):
            entry["low_text_pages"].append(page.metadata["page"])
        if page.metadata.get("blank"):
            entry["blank_pages"].append(page.metadata["page"])
    return report


def write_atomically(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temporary_path.write_text(text, encoding="utf-8")
    # On Windows, replacing fails while the API is reading the file.
    for attempt in range(10):
        try:
            temporary_path.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                temporary_path.unlink(missing_ok=True)
                raise
            sleep(0.05 * (attempt + 1))


def publish_index_version(marker_path):
    write_atomically(marker_path, uuid4().hex)


def process_documents(data_dir=DATA_DIR, db=None, marker_path=None):
    if marker_path is None and db is None:
        marker_path = INDEX_VERSION_PATH
    data_dir = Path(data_dir)
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        print(f"Created {data_dir} directory. Add your PDF files here.")

    all_docs = []
    print("Step 1: Loading documents...")
    for path in sorted(data_dir.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            filename = path.name
            docs = extract_pdf(path)
            provenance = infer_document_provenance([doc.page_content for doc in docs[:2]])
            
            for i, doc in enumerate(docs):
                doc.metadata["source"] = filename
                doc.metadata["page"] = i + 1
                doc.metadata.update(provenance)
                doc.page_content = f"Source: {filename} | Page: {i + 1}\n{doc.page_content}"
            
            all_docs.extend(docs)
            weak_pages = [doc.metadata["page"] for doc in docs if doc.metadata.get("low_text")]
            if weak_pages:
                print(f"Warning: {filename} has little or no extracted text on pages {weak_pages}.")
    
    if marker_path is not None:
        write_atomically(Path(marker_path).with_name(PAGE_REPORT_NAME), json.dumps(page_report(all_docs), indent=2))

    if not all_docs:
        if db is None:
            db = get_vector_db()
        ids = db.get(include=[])["ids"]
        for start in range(0, len(ids), 100):
            db.delete(ids=ids[start : start + 100])
        if marker_path is not None and (ids or not Path(marker_path).exists()):
            publish_index_version(marker_path)
        print(f"No PDFs found in {data_dir}; cleared the stored corpus.")
        return

    print("Step 2: Chunking text...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", "!", "?", ",", " "]
    )
    
    chunks = split_section_documents(all_docs, text_splitter)
    print(f"Split {len(all_docs)} pages into {len(chunks)} contextualized chunks.")

    print("Step 3: Ingesting into Vector Store...")
    if db is None:
        db = get_vector_db()

    existing = db.get(include=["documents", "metadatas"])
    existing_by_id = {
        chunk_id: (content, metadata)
        for chunk_id, content, metadata in zip(
            existing["ids"], existing["documents"], existing["metadatas"]
        )
    }
    page_chunk_counts = defaultdict(int)
    desired_ids = []
    changed_chunks = []
    changed_ids = []
    for chunk in chunks:
        source = chunk.metadata["source"]
        page = chunk.metadata["page"]
        page_key = (source, page)
        ordinal = page_chunk_counts[page_key]
        page_chunk_counts[page_key] += 1
        chunk_id = sha256(f"{source}\0{page}\0{ordinal}".encode()).hexdigest()
        desired_ids.append(chunk_id)
        if existing_by_id.get(chunk_id) != (chunk.page_content, chunk.metadata):
            changed_chunks.append(chunk)
            changed_ids.append(chunk_id)

    for start in range(0, len(changed_chunks), 100):
        db.add_documents(
            changed_chunks[start : start + 100],
            ids=changed_ids[start : start + 100],
        )

    stale_ids = set(existing["ids"]) - set(desired_ids)
    stale_ids = sorted(stale_ids)
    for start in range(0, len(stale_ids), 100):
        db.delete(ids=stale_ids[start : start + 100])
    if marker_path is not None and (changed_ids or stale_ids or not Path(marker_path).exists()):
        publish_index_version(marker_path)
    print(f"Success! Stored {len(desired_ids)} chunks from {len(all_docs)} pages.")

if __name__ == "__main__":
    process_documents()
