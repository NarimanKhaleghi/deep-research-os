"""Unit tests — text normalization, number matching, front-matter, ids."""

from __future__ import annotations

from lib import util


def test_next_id_increments():
    assert util.next_id("SRC", []) == "SRC-0001"
    assert util.next_id("SRC", ["SRC-0001", "SRC-0007", "junk"]) == "SRC-0008"
    assert util.next_id("CX", ["CX-0003"]) == "CX-0004"


def test_slugify_handles_fa_and_punctuation():
    assert util.slugify("Does X affect Y?") == "does-x-affect-y"
    assert util.slugify("سلام دنیا") == "سلام-دنیا"
    assert util.slugify("...") == "project"


def test_parse_front_matter_block_and_inline_lists():
    text = (
        "---\n"
        "title: \"Hello world\"\n"
        "profile: deep\n"
        "privacy_mode: false\n"
        "count: 3\n"
        "success_criteria:\n"
        "  - \"one\"\n"
        "  - two\n"
        "angles: [a, b]\n"
        "---\n"
        "# Body\n"
    )
    meta, body = util.parse_front_matter(text)
    assert meta["title"] == "Hello world"
    assert meta["profile"] == "deep"
    assert meta["privacy_mode"] is False
    assert meta["count"] == 3
    assert meta["success_criteria"] == ["one", "two"]
    assert meta["angles"] == ["a", "b"]
    assert body.startswith("# Body")


def test_numbers_match_precision_rules():
    q = [{"raw": "96.555%", "value": 96.555, "unit": "%", "decimals": 3}]
    assert util.numbers_match({"value": 96.555, "unit": "%", "decimals": 3}, q)
    # rounding *up* to a coarser precision is forbidden (97 from 96.555 fails)
    assert not util.numbers_match({"value": 97, "unit": "%", "decimals": 0}, q)
    # kept precision, exact value
    assert util.numbers_match({"value": 84, "unit": None, "decimals": 0},
                              [{"raw": "84%", "value": 84.0, "unit": "%", "decimals": 0}])
    # thousands separators collapse
    assert util.numbers_match({"value": 1000, "unit": None, "decimals": 0},
                              util.extract_numbers("about 1,000 units"))


def test_extract_numbers_persian():
    nums = util.extract_numbers("رشد ۹۶٫۵٪ در سال ۱۴۰۳")
    values = {(n["value"], n["unit"]) for n in nums}
    assert (96.5, "%") in values
    assert (1403, None) in values


def test_normalize_text_zwnj_and_case():
    assert util.normalize_text("می‌رود") == util.normalize_text("میرود")
    assert util.normalize_text("Hello   WORLD") == "hello world"


def test_quote_in_text_fuzzy_and_exact():
    hay = "Participants lost 2.3% lean mass over 8 weeks of training."
    ok, start, _ = util.quote_in_text("lost 2.3% lean mass", hay)
    assert ok and start is not None
    ok2, _, _ = util.quote_in_text("lost 3.3% lean mass", hay, threshold=0.95)
    assert not ok2


def test_md_sections_and_bullets():
    text = "## A\n- one\n- two\ntext\n\n## B\n| x | y |\n| - | - |\n"
    sections = util.md_sections(text)
    assert set(sections) == {"a", "b"}
    assert util.count_bullets(sections["a"]) == 2


def test_domain_of():
    assert util.domain_of("https://www.example.co.uk/path") == "example.co.uk"
    assert util.domain_of("https://cdc.gov/data") == "cdc.gov"
    assert util.domain_of("https://sub.example.org/x") == "example.org"
