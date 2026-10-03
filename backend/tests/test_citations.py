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


def test_a_statement_without_an_id_is_detected():
    answer = "Thirty days. [c1] Also ten days. Fine print applies! [c2]"
    assert uncited_statements(answer) == ["Also ten days."]
    assert uncited_statements("Thirty days. [c1]") == []
