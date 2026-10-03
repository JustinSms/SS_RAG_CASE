from app.ingestion.parser import Page
from app.ingestion.sections import ROOT_HEADING, build_sections
from env.config import settings


def test_headings_become_a_tree_with_heading_paths():
    pages = [Page(1, "# 1 Intro\n\nHello.\n\n## 1.1 Aim\n\nAim text.\n\n# 2 Scope\n\n## 2.1 Data\n\nData text.")]
    sections = build_sections(pages)

    assert [s.heading for s in sections] == ["1 Intro", "1.1 Aim", "2 Scope", "2.1 Data"]
    assert [s.position for s in sections] == [0, 1, 2, 3]
    assert [s.parent for s in sections] == [None, 0, None, 2]
    assert [s.level for s in sections] == [1, 2, 1, 2]
    assert sections[3].heading_path == "2 Scope > 2.1 Data"
    assert sections[1].paragraphs[0].text == "Aim text."


def test_text_before_the_first_heading_goes_into_a_root_section():
    sections = build_sections([Page(1, "Cover text.\n\n# 1 Intro\n\nBody.")])

    assert sections[0].heading == ROOT_HEADING
    assert sections[0].paragraphs[0].text == "Cover text."
    assert sections[0].parent is None
    assert sections[1].heading == "1 Intro"


def test_skipped_level_attaches_to_the_nearest_shallower_heading():
    sections = build_sections([Page(1, "# A\n\n### C\n\nText.")])
    assert sections[1].parent == 0
    assert sections[1].heading_path == "A > C"


def test_page_range_follows_the_text_and_paragraphs_keep_their_page():
    pages = [Page(1, "# A\n\nOne."), Page(2, "Two.\n\n# B\n\nThree.")]
    sections = build_sections(pages)

    assert (sections[0].page_start, sections[0].page_end) == (1, 2)
    assert [p.page for p in sections[0].paragraphs] == [1, 2]
    assert (sections[1].page_start, sections[1].page_end) == (2, 2)


def test_bold_markers_are_removed_from_headings():
    assert build_sections([Page(1, "## **2.1 Data**\n\nx")])[0].heading == "2.1 Data"


def test_a_heading_without_text_is_kept_as_an_empty_section():
    sections = build_sections([Page(1, "# A\n\n## B\n\nText.")])
    assert sections[0].paragraphs == []
    assert len(sections) == 2


def test_no_headings_gives_pseudo_sections_of_max_chunk_size(monkeypatch):
    monkeypatch.setattr(settings, "MAX_CHUNK_SIZE", 10)
    paragraph = "x" * 20  # 5 tokens at 4 characters per token
    pages = [Page(1, f"{paragraph}\n\n{paragraph}\n\n{paragraph}"), Page(2, paragraph)]
    sections = build_sections(pages)

    assert [s.heading for s in sections] == ["Part 1", "Part 2"]
    assert [len(s.paragraphs) for s in sections] == [2, 2]
    assert (sections[1].page_start, sections[1].page_end) == (1, 2)
    assert all(s.parent is None for s in sections)
