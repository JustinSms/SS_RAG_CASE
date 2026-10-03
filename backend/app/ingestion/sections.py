import re
from dataclasses import dataclass, field

from app.ingestion.parser import Page
from app.ingestion.tokens import count_tokens
from env.config import settings

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
ROOT_HEADING = "Start of document"


@dataclass
class Paragraph:
    text: str
    page: int


@dataclass
class SectionDraft:
    heading: str
    level: int
    heading_path: str  # e.g. "2 Scope > 2.1 Data"
    position: int  # order in document
    parent: int | None  # position of the parent section
    page_start: int
    page_end: int
    paragraphs: list[Paragraph] = field(default_factory=list)


def build_sections(pages: list[Page]) -> list[SectionDraft]:
    """A4: headings become a section tree, in document order."""
    sections: list[SectionDraft] = []
    path: list[SectionDraft] = []  # the open sections from the top level down to the current one
    current: SectionDraft | None = None
    has_headings = False

    for page in pages:
        lines: list[str] = []

        def flush_paragraph():
            nonlocal current
            text = "\n".join(lines).strip()
            lines.clear()
            if not text:
                return
            if current is None:  # text before the first heading
                current = SectionDraft(ROOT_HEADING, 1, ROOT_HEADING, 0, None, page.number, page.number)
                sections.append(current)
            current.paragraphs.append(Paragraph(text, page.number))
            current.page_end = page.number

        for line in page.markdown.splitlines():
            match = HEADING.match(line)
            heading = clean_heading(match.group(2)) if match else ""
            if heading:
                flush_paragraph()
                has_headings = True
                level = len(match.group(1))
                while path and path[-1].level >= level:
                    path.pop()
                current = SectionDraft(
                    heading=heading,
                    level=level,
                    heading_path=" > ".join([s.heading for s in path] + [heading]),
                    position=len(sections),
                    parent=path[-1].position if path else None,
                    page_start=page.number,
                    page_end=page.number,
                )
                sections.append(current)
                path.append(current)
            elif line.strip():
                lines.append(line)
            else:
                flush_paragraph()
        flush_paragraph()

    if not has_headings:
        return pseudo_sections(sections)
    return sections


def clean_heading(text: str) -> str:
    return re.sub(r"[*_`]", "", text).strip()


def pseudo_sections(sections: list[SectionDraft]) -> list[SectionDraft]:
    """No headings found: cut the text into parts of about MAX_CHUNK_SIZE tokens."""
    paragraphs = [p for s in sections for p in s.paragraphs]
    parts: list[SectionDraft] = []
    size = 0
    for paragraph in paragraphs:
        tokens = count_tokens(paragraph.text)
        if not parts or size + tokens > settings.MAX_CHUNK_SIZE:
            name = f"Part {len(parts) + 1}"
            parts.append(SectionDraft(name, 1, name, len(parts), None, paragraph.page, paragraph.page))
            size = 0
        parts[-1].paragraphs.append(paragraph)
        parts[-1].page_end = paragraph.page
        size += tokens
    return parts
