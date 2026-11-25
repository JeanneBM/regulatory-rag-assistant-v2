"""Qualifiers on a particular cross-reference must retain their local scope."""
import pytest

from regrag.verification import rule_check

QUOTE = "The representative shall verify that obligations in Article 7 and, where applicable, Article 8 are fulfilled."


def claim(statement, quote=QUOTE):
    return {"statement": statement, "quote": quote, "act": "AI_ACT", "article": "1",
            "label": "Article 1", "citation": "Fixture Article 1"}


@pytest.mark.parametrize("statement", [
    "The representative shall verify that obligations in Article 7 are fulfilled.",
    "Przedstawiciel musi sprawdzić spełnienie obowiązków z art. 7.",
    "The representative shall verify obligations in Article 8 where applicable.",
])
def test_a_qualifier_does_not_spread_to_another_article_reference(statement):
    assert rule_check(claim(statement)) is None


@pytest.mark.parametrize("statement", [
    "The representative shall verify that obligations in Article 8 are fulfilled.",
    "The representative shall verify obligations in Article 7 and Article 8.",
])
def test_the_qualified_article_cannot_be_made_unconditional(statement):
    verdict = rule_check(claim(statement))
    assert verdict["support"] == "partial" and "where applicable" in verdict["note"]


def test_a_later_qualifier_is_checked_after_an_unrelated_qualified_reference():
    quote = QUOTE + " The representative shall maintain records where applicable."
    statement = "The representative shall verify obligations in Article 7 and maintain records."
    verdict = rule_check(claim(statement, quote))
    assert verdict["support"] == "partial" and "where applicable" in verdict["note"]
