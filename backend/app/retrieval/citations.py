"""B8: map the [cXX] ids in an answer to stored sources, and drop ids that are not in the context."""

import re
from dataclasses import dataclass

# A bracket made only of ids: "[c3]" or "[c3, c7]".
CITATION = re.compile(r"\[\s*(c\d+(?:\s*,\s*c\d+)*)\s*\]")
# Same, with the space before it, so removing a bracket leaves no double space.
LEADING_SPACE_CITATION = re.compile(r"( ?)" + CITATION.pattern)


@dataclass
class Source:
    label: str  # "c12"
    document_id: str
    filename: str
    page_start: int
    page_end: int
    heading_path: str
    cosine: float | None = None  # B2 score; None for a chunk added by section selection
    rerank: float | None = None  # B3 score; None if the reranker failed or the chunk was selected


def clean_citations(answer: str, sources: dict[str, Source]) -> str:
    """Keep only ids that exist in `sources`; a bracket with no valid id disappears."""

    def fix(match: re.Match) -> str:
        ids = [i.strip() for i in match.group(2).split(",")]
        valid = [i for i in ids if i in sources]
        return f"{match.group(1)}[{', '.join(valid)}]" if valid else ""

    return LEADING_SPACE_CITATION.sub(fix, answer)


def strip_citations(text: str) -> str:
    """Remove all citation brackets (used for earlier answers sent back as history)."""
    return LEADING_SPACE_CITATION.sub("", text)


def uncited_statements(answer: str) -> list[str]:
    """Text with no citation after it, so a prompt that stops citing is easy to detect.

    The answer prompt cites at the end of a sentence or short paragraph, once for several
    sentences from the same chunks. So within each line (a paragraph or list item), the text after
    the last citation is uncited. A line ending in ":" introduces a list and needs no citation.
    """
    uncited = []
    for line in answer.splitlines():
        rest = CITATION.split(line)[-1].strip()
        if rest and not rest.endswith(":"):
            uncited.append(rest)
    return uncited
