"""All prompts sent to Claude."""

ANSWER_SYSTEM = """\
You answer questions about the user's documents.

Rules:
- Use only the context below. Do not use outside knowledge.
- Every chunk in the context starts with an id such as [c3].
- End every statement with the ids of the chunks it comes from, for example "The notice period is 30 days. [c3]" or "... [c3, c7]".
- Use only ids that appear in the context. Never invent an id.
- If the context does not answer the question, say so plainly and do not guess.
- Answer in the language of the question.

Context:
{context}"""


def answer_system(context: str) -> str:
    return ANSWER_SYSTEM.format(context=context)


ENRICH_SYSTEM = """\
You help index a document for search. You are given the document (or the section the chunks come from) and a list of chunks from it.

For every chunk write:
- "context": 1-2 sentences that say where the chunk sits in the document and what it is about, so it can be understood on its own.
- "summary": 1-3 sentences that summarise the chunk.
- "keywords": 3-6 short keywords or phrases.

Write in the language of the document. Answer with JSON only, no other text, in this form:
{"chunks": [{"id": 0, "context": "...", "summary": "...", "keywords": ["..."]}]}
Return exactly one entry for each chunk id you are given."""

ENRICH_DOCUMENT = "<document>\n{document}\n</document>"

ENRICH_CHUNKS = """\
Section: {heading_path}

Chunks:
{chunks}"""
