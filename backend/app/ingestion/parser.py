import re
from dataclasses import dataclass

import pymupdf
import pymupdf4llm


# PyMuPDF4LLM marks styled text with HTML tags: <mark> for text on a coloured background, <u> for
# underlined text (often links), <sup>/<sub> for raised or lowered text. They end up in headings,
# heading paths and chunk text, so they are removed and the text is kept. <br> is kept: it is a line
# break inside a table cell.
FORMAT_TAGS = re.compile(r"</?(?:mark|u|sup|sub)>")


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
    pages = [Page(c["metadata"]["page_number"], strip_format_tags(c["text"])) for c in chunks]
    if not any(page.markdown.strip() for page in pages):
        raise NoTextError("No text found in this PDF (scanned documents are not supported).")
    return pages


def strip_format_tags(markdown: str) -> str:
    """'# <mark>Title</mark>' -> '# Title'."""
    return FORMAT_TAGS.sub("", markdown)
