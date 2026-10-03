"""A6: Haiku writes a context sentence, a summary and keywords for every chunk."""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from app.ingestion.tokens import count_tokens
from app.llm.client import complete
from app.llm.prompts import ENRICH_CHUNKS, ENRICH_DOCUMENT, ENRICH_SYSTEM
from env.config import settings

log = logging.getLogger(__name__)


@dataclass
class Enrichment:
    context: str
    summary: str
    keywords: list[str]


@dataclass
class SectionJob:
    heading_path: str
    section_text: str  # sent instead of the document when the document is too big
    chunk_texts: list[str]


def enrich_sections(document_text: str, jobs: list[SectionJob], on_section_done) -> list[list[Enrichment | None]]:
    """Enrich every section; `on_section_done(index)` runs in the calling thread as each one finishes.

    Returns, per section, one entry per chunk: an Enrichment, or None if it could not be enriched.
    """
    results: list[list[Enrichment | None]] = [[None] * len(job.chunk_texts) for job in jobs]
    if not jobs:
        return results

    # The first call writes the prompt cache; the rest read it instead of paying for the document again.
    results[0] = enrich_section(document_text, jobs[0])
    on_section_done(0)

    with ThreadPoolExecutor(max_workers=settings.ENRICH_CONCURRENCY) as pool:
        futures = {pool.submit(enrich_section, document_text, job): i for i, job in enumerate(jobs) if i > 0}
        for future in as_completed(futures):
            i = futures[future]
            results[i] = future.result()  # enrich_section never raises
            on_section_done(i)
    return results


def enrich_section(document_text: str, job: SectionJob) -> list[Enrichment | None]:
    """One call per group of ENRICH_BATCH_SIZE chunks. A failed group stays unenriched."""
    if count_tokens(document_text) > settings.ENRICH_DOC_MAX_TOKENS:
        document_text = job.section_text

    batch = settings.ENRICH_BATCH_SIZE
    results: list[Enrichment | None] = []
    for start in range(0, len(job.chunk_texts), batch):
        group = job.chunk_texts[start : start + batch]
        results.extend(enrich_group(document_text, job.heading_path, group))
    return results


def enrich_group(document_text: str, heading_path: str, texts: list[str]) -> list[Enrichment | None]:
    chunks = "\n\n".join(f"[{i}]\n{text}" for i, text in enumerate(texts))
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": ENRICH_DOCUMENT.format(document=document_text),
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": ENRICH_CHUNKS.format(heading_path=heading_path, chunks=chunks)},
            ],
        }
    ]
    for attempt in range(1 + settings.ENRICH_RETRIES):
        try:
            reply = complete(settings.ENRICH_MODEL, ENRICH_SYSTEM, messages, settings.ENRICH_MAX_TOKENS)
            return parse_enrichments(reply, len(texts))
        except Exception as error:  # enrichment never fails a document
            log.warning("Enrichment try %d failed for %r: %s", attempt + 1, heading_path, error)
    return [None] * len(texts)


def parse_enrichments(reply: str, count: int) -> list[Enrichment]:
    """The JSON must hold one valid entry for each of the `count` chunk ids."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.strip())
    entries = json.loads(text)["chunks"]
    by_id = {}
    for entry in entries:
        keywords = entry["keywords"]
        if not all(isinstance(entry[key], str) for key in ("context", "summary")) or not (
            isinstance(keywords, list) and all(isinstance(k, str) for k in keywords)
        ):
            raise ValueError("wrong field types")
        by_id[entry["id"]] = Enrichment(entry["context"].strip(), entry["summary"].strip(), keywords)
    if set(by_id) != set(range(count)):
        raise ValueError(f"expected chunk ids 0-{count - 1}, got {sorted(by_id)}")
    return [by_id[i] for i in range(count)]
