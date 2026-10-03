from dataclasses import dataclass

import pymupdf
import pymupdf4llm


class NoTextError(Exception):
    pass


@dataclass
class Page:
    number: int  # 1-based, as printed in the viewer
    markdown: str


def parse_pdf(path: str) -> list[Page]:
    """A3: PDF to markdown, one entry per page. Headings come out as '#' lines."""
    with pymupdf.open(path) as document:
        chunks = pymupdf4llm.to_markdown(document, page_chunks=True)
    pages = [Page(c["metadata"]["page_number"], c["text"]) for c in chunks]
    if not any(page.markdown.strip() for page in pages):
        raise NoTextError("No text found in this PDF (scanned documents are not supported).")
    return pages
