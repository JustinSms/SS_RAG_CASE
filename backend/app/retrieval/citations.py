"""B8: map the [cXX] ids in an answer to stored sources, and drop ids that are not in the context."""

import re
from dataclasses import dataclass

# A bracket made only of ids: "[c3]" or "[c3, c7]".
CITATION = re.compile(r"\[\s*(c\d+(?:\s*,\s*c\d+)*)\s*\]")
# Same, with the space before it, so removing a bracket leaves no double space.
LEADING_SPACE_CITATION = re.compile(r"( ?)" + CITATION.pattern)
# A sentence ends at a full stop (unless a citation follows it) or after a closing bracket.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?!\[c)|(?<=\])\s+")


@dataclass
class Source:
    label: str  # "c12"
    document_id: str
    filename: str
    page_start: int
    page_end: int
    heading_path: str


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
    """Sentences without a citation, so a prompt that stops citing is easy to detect."""
    sentences = [s.strip() for s in SENTENCE_END.split(answer) if s.strip()]
    return [s for s in sentences if not CITATION.search(s)]
