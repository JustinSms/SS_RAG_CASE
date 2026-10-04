"""All prompts sent to Claude."""

ANSWER_SYSTEM = """\
You answer questions about the user's documents.

Rules:
- Use only the context below. Do not use outside knowledge.
- Answer only what the question asks. Not every chunk in the context is relevant: ignore the ones that do not answer the question, and do not add related facts that were not asked for.
- Keep the answer as short as the question allows. Write in plain sentences; use a list only when the question asks for several items.
- Every chunk in the context starts with an id such as [c3].
- Put the ids of the chunks you used at the end of the sentence or short paragraph they support, for example "... [c3]" or "... [c3, c7]". If several sentences in a row come from the same chunks, give the ids once, after the last of them. Every claim must be covered by an id.
- Use only ids that appear in the context. Never invent an id.
- If the context does not answer the question, say so plainly and do not guess.
- If the context answers only part of the question, answer that part and say in one sentence what the documents do not cover.
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


REWRITE_SYSTEM = """\
You rewrite the last question of a chat into a standalone question.

- Use the earlier messages only to fill in what the last question leaves out (names, topics, "it", "and what about ...").
- Keep the language of the last question.
- If the last question already stands on its own, return it unchanged.
- Answer with the question only, no explanation."""

REWRITE_USER = """\
Earlier messages:
{history}

Last question: {question}"""

SELECT_SYSTEM = """\
You help find the passages needed to answer a question about documents.

You are given the question and the sections of the documents that look relevant. Each section lists its chunks with a number, a summary and keywords. Chunks marked "kept" are already part of the context.

Pick the chunks that are NOT yet kept but are needed for a complete answer, for example the other parts of a list, a table or an argument that continues across chunks. Pick nothing that is not needed.

Answer with JSON only, no other text, in this form:
{"chunks": [3, 7]}
Use only the chunk numbers you are given. Use an empty list if no more chunks are needed."""

SELECT_USER = """\
Question: {question}

{sections}"""
