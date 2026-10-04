from app.retrieval.citations import (
    Source,
    clean_citations,
    strip_citations,
    uncited_statements,
)


def source(label: str) -> Source:
    return Source(label, "doc-1", "Contract.pdf", 12, 13, "3 Terms > 3.1 Scope")


SOURCES = {"c1": source("c1"), "c2": source("c2")}


def test_known_ids_are_kept():
    assert clean_citations("Thirty days. [c1]", SOURCES) == "Thirty days. [c1]"
    assert clean_citations("Both agree. [c1, c2]", SOURCES) == "Both agree. [c1, c2]"


def test_unknown_ids_are_dropped():
    assert clean_citations("Thirty days. [c9]", SOURCES) == "Thirty days."
    assert clean_citations("Both agree. [c1, c9]", SOURCES) == "Both agree. [c1]"


def test_other_brackets_are_left_alone():
    assert clean_citations("See [1] and [note]. [c1]", SOURCES) == "See [1] and [note]. [c1]"


def test_strip_citations_removes_every_bracket():
    assert strip_citations("A. [c1] B. [c1, c2]") == "A. B."


def test_sentences_can_share_one_citation_at_the_end():
    assert uncited_statements("Thirty days. Also ten days. Fine print applies! [c2]") == []
    assert uncited_statements("Thirty days. [c1] Ten days in writing. [c1, c2]") == []


def test_text_after_the_last_citation_of_a_paragraph_is_detected():
    answer = "Thirty days. [c1] Also ten days.\n\nFine print applies. [c2] Nothing else."
    assert uncited_statements(answer) == ["Also ten days.", "Nothing else."]


def test_a_list_intro_needs_no_citation_but_each_item_does():
    answer = "The fees are:\n- Ten euros. [c1]\n- Twenty euros."
    assert uncited_statements(answer) == ["- Twenty euros."]
