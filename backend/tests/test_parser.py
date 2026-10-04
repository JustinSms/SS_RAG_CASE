from app.ingestion.parser import strip_format_tags


def test_format_tags_are_removed_and_their_text_kept():
    assert strip_format_tags("# <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark>") == "# The NIST Cybersecurity Framework (CSF) 2.0"
    assert strip_format_tags("See <u>https://doi.org/10.3386/w32487</u>.") == "See https://doi.org/10.3386/w32487."
    assert strip_format_tags("## <sup>RESEARCH STARTER</sup>") == "## RESEARCH STARTER"


def test_table_line_breaks_and_comparisons_are_kept():
    assert strip_format_tags("| a<br>b | x < 5 |") == "| a<br>b | x < 5 |"
