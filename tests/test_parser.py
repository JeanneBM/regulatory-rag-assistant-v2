import pytest

from conftest import BODY, act_document, article_html, point_table
from regrag.parser import MAX_UNIT_CHARS, ParseError, corpus_stats, parse_act, require_coverage
from regrag.sources import ACTS

DORA = ACTS["DORA"]


def parse(body: str, title="Prohibited AI practices", number=1, act=DORA):
    return parse_act(act_document(1, {1: article_html(number, body, title)}, chapters=False), act)


def test_numbered_paragraphs_become_citable_units_with_titles_and_anchors():
    units = parse_act(act_document(3), DORA)
    assert [u["label"] for u in units[:2]] == ["Article 1(1)", "Article 1(2)"]
    assert units[0]["id"] == "DORA-art-1-par-1"
    assert units[0]["article_title"] == "Title of article 1"
    assert units[0]["text"].startswith("1. Financial entities")
    assert units[0]["url"].endswith("CELEX:32022R2554#art_1")
    assert [u["ordinal"] for u in units] == list(range(len(units)))


def test_point_units_carry_lead_in_and_sub_point_conditions():
    body = ("<div><p class='oj-normal'>1.   The following AI practices shall be prohibited:</p>"
            + point_table([("a", "subliminal techniques;"),
                           ("c", "social scoring leading to either or both of the following:")],
                          nested={"c": [("i", "detrimental treatment in unrelated contexts;"),
                                        ("ii", "unjustified or disproportionate treatment;")]})
            + "<p class='oj-normal'>The prohibition in point (c) applies without prejudice to "
              "<a href='#'>Article 6</a>.</p></div>")
    units = parse(body)
    by_label = {u["label"]: u for u in units}
    point_c = by_label["Article 1(1), point (c)"]
    assert point_c["id"] == "DORA-art-1-par-1-pt-c"
    assert point_c["text"].splitlines() == [
        "1. The following AI practices shall be prohibited:",
        "(c) social scoring leading to either or both of the following:",
        "(i) detrimental treatment in unrelated contexts;",
        "(ii) unjustified or disproportionate treatment;",
    ]
    tail = by_label["Article 1(1)"]
    assert tail["text"] == "The prohibition in point (c) applies without prejudice to Article 6."
    assert "(i)" not in by_label["Article 1(1), point (a)"]["text"]


def test_repeated_point_lists_in_one_paragraph_get_unique_ids():
    body = ("<div><p class='oj-normal'>1.   Financial entities shall:</p>"
            + point_table([("a", "identify risks;"), ("b", "document them;")])
            + "<p class='oj-normal'>In addition, they shall:</p>"
            + point_table([("a", "report incidents;")]) + "</div>")
    units = parse(body)
    assert [u["id"] for u in units] == ["DORA-art-1-par-1-pt-a", "DORA-art-1-par-1-pt-b",
                                        "DORA-art-1-par-1-pt-a-dup2"]
    assert units[2]["text"] == "In addition, they shall:\n(a) report incidents;"
    assert units[0]["text"] == "1. Financial entities shall:\n(a) identify risks;"


def test_unnumbered_article_and_inline_markup_stay_in_sentence():
    body = ("<p class='oj-normal'>Providers <span class='oj-italic'>shall</span> take measures"
            "<span class='oj-super'><a>(1)</a></span> referred to in <a href='#'>Article 6</a>."
            "<!-- editorial note --></p>")
    [unit] = parse(body, title="AI literacy")
    assert unit["label"] == "Article 1" and unit["paragraph"] is None
    assert unit["text"] == "Providers shall take measures(1) referred to in Article 6."


def test_chapter_headings_annex_and_signature_are_excluded():
    units = parse_act(act_document(11), DORA)
    joined = "\n".join(u["text"] for u in units)
    for excluded in ("CHAPTER", "GENERAL PROVISIONS", "Done at", "Annex text", "binding in its entirety"):
        assert excluded not in joined
    assert "Recital" not in joined


def test_quoted_lettered_and_out_of_sequence_headings_do_not_split_articles():
    body = (f"<div><p class='oj-normal'>1.   {BODY}</p></div>"
            "<p class='oj-normal'>Article 7a</p><p class='oj-normal'>Article 9</p>"
            f"<p class='oj-normal'>Quoted amendment text that belongs to article one.</p>")
    units = parse(body)
    assert {u["article"] for u in units} == {"1"}
    assert "Article 7a\nArticle 9" in units[0]["text"]


def test_long_paragraph_is_split_between_lines_and_words():
    long_line = " ".join(["regulation"] * 900)
    body = f"<div><p class='oj-normal'>1.   {long_line}</p><p class='oj-normal'>{long_line}</p></div>"
    units = parse(body)
    assert len(units) > 2
    assert all(len(u["text"]) <= MAX_UNIT_CHARS for u in units)
    assert units[0]["id"].endswith("-part-1")
    words = sum(len(u["text"].replace("1. ", "", 1).split()) for u in units)
    assert words == 1800


def test_coverage_fails_closed_for_missing_or_extra_articles():
    units = parse_act(act_document(DORA.articles), DORA)
    require_coverage(units, DORA)
    with pytest.raises(ParseError, match="missing"):
        require_coverage([u for u in units if u["article"] != "17"], DORA)
    with pytest.raises(ParseError, match="beyond"):
        require_coverage(parse_act(act_document(DORA.articles + 1), DORA), DORA)


def test_bot_challenge_page_is_rejected():
    with pytest.raises(ParseError, match="bot challenge"):
        parse_act("<html><body><p>Please verify you are human</p></body></html>", DORA)


def test_stats_summarise_structure():
    stats = corpus_stats(parse_act(act_document(5), DORA))["DORA"]
    assert stats["articles"] == 5 and stats["units"] == 10
    assert stats["with_paragraph"] == 10 and stats["anchored"] == 10
