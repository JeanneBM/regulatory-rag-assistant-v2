import pytest

from conftest import FakeOpenAI, completion
from regrag.generation import strip_excerpt_references
from regrag.verification import ModelVerifier, governing_text, rule_check, verdict_schema, verify_claims

BOARD = ("The Board shall advise and assist the Commission and the Member States. To that end, the Board "
         "may in particular:\n(f) support the Commission in promoting AI literacy;")
LITERACY = ("Providers and deployers of AI systems shall take measures to ensure, to their best extent, a "
            "sufficient level of AI literacy of their staff.")
EMOTION = ("3. Deployers of an emotion recognition system shall inform the natural persons exposed thereto of "
           "the operation of the system. This obligation shall not apply to AI systems permitted by law to "
           "detect, prevent or investigate criminal offences.")
SCORING = "1. The following AI practices shall be prohibited:\n(c) the use of AI systems for social scoring;"
PROFILING = ("Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be "
             "considered to be high-risk where the AI system performs profiling of natural persons.")


def claim(statement, quote, label="Article 1", article="1"):
    return {"statement": statement, "quote": quote, "label": label, "article": article, "act": "AI_ACT",
            "citation": f"AI Act {label}"}


def test_governing_text_of_a_point_is_the_last_introductory_sentence_and_the_point():
    assert governing_text(BOARD) == ("To that end, the Board may in particular: "
                                     "(f) support the Commission in promoting AI literacy;")
    assert governing_text(LITERACY) == LITERACY


@pytest.mark.parametrize("statement", [
    "The Board shall support the Commission in promoting AI literacy.",
    "The Board must support the Commission in promoting AI literacy.",
    "Rada musi wspierać Komisję w promowaniu kompetencji w zakresie AI.",
])
def test_a_power_presented_as_an_obligation_is_partial(statement):
    verdict = rule_check(claim(statement, BOARD, "Article 66, point (f)", "66"))
    assert verdict["support"] == "partial" and "power" in verdict["note"]


@pytest.mark.parametrize("statement", [
    "The Board may support the Commission in promoting AI literacy.",
    "Rada może wspierać Komisję w promowaniu kompetencji w zakresie AI.",
])
def test_a_power_kept_as_a_power_passes(statement):
    assert rule_check(claim(statement, BOARD, "Article 66, point (f)", "66")) is None


def test_an_obligation_weakened_to_an_option_is_partial():
    quote = "Deployers shall inform the natural persons exposed thereto of the operation of the system."
    verdict = rule_check(claim("Deployers may inform the persons exposed of the operation of the system.", quote))
    assert verdict["support"] == "partial" and "weakens" in verdict["note"]


def test_idioms_with_may_do_not_count_as_a_power():
    quote = "Providers shall notify the authority or the Commission, as the case may be."
    assert rule_check(claim("Providers must notify the authority or the Commission.", quote)) is None


def test_an_invented_exception_is_partial_and_a_real_one_passes():
    verdict = rule_check(claim("Social scoring is prohibited, with exceptions for research.", SCORING,
                               "Article 5(1), point (c)", "5"))
    assert verdict["support"] == "partial" and "does not contain" in verdict["note"]
    assert rule_check(claim("Social scoring is prohibited.", SCORING, "Article 5(1), point (c)", "5")) is None


@pytest.mark.parametrize("statement, passes", [
    ("Deployers of an emotion recognition system must inform the persons exposed of its operation.", False),
    ("Deployers of an emotion recognition system must inform the persons exposed of its operation, "
     "except for systems permitted by law to investigate criminal offences.", True),
    ("Podmioty stosujące system rozpoznawania emocji muszą informować osoby, z wyjątkiem systemów "
     "dopuszczonych prawem do ścigania przestępstw.", True),
])
def test_an_exception_of_the_text_must_be_kept(statement, passes):
    verdict = rule_check(claim(statement, EMOTION, "Article 50(3)", "50"))
    assert (verdict is None) is passes
    if not passes:
        assert "omits an exception" in verdict["note"]


@pytest.mark.parametrize("statement, passes", [
    ("Providers and deployers must ensure a sufficient level of AI literacy of their staff.", False),
    ("Providers and deployers must take measures to ensure, to their best extent, AI literacy of their staff.", True),
    ("Dostawcy i podmioty stosujące muszą w miarę możliwości zapewnić kompetencje w zakresie AI personelu.", True),
])
def test_a_limiting_qualifier_must_be_kept(statement, passes):
    verdict = rule_check(claim(statement, LITERACY, "Article 4", "4"))
    assert (verdict is None) is passes


def test_an_annex_that_limits_scope_must_be_kept():
    verdict = rule_check(claim("High-risk AI systems that perform profiling are always high-risk.", PROFILING,
                               "Article 6(3)", "6"))
    assert verdict["support"] == "partial" and "Annex III" in verdict["note"]
    kept = "An AI system referred to in Annex III is always high-risk where it performs profiling of natural persons."
    assert rule_check(claim(kept, PROFILING, "Article 6(3)", "6")) is None


def test_figure_rule_ignores_excerpt_ids_left_in_a_statement():
    quote = "Providers shall keep the documentation up to date."
    assert rule_check(claim("Providers must keep the documentation up to date (E3).", quote)) is None


@pytest.mark.parametrize("raw, clean", [
    ("Social scoring is prohibited (E1).", "Social scoring is prohibited."),
    ("The scope excludes personal use (E2, E3).", "The scope excludes personal use."),
    ("Persons must be informed, unless it is obvious, as per E1.", "Persons must be informed, unless it is obvious."),
    ("Information comes at the first interaction, according to E3.", "Information comes at the first interaction."),
    ("Providers must, according to E1, inform users.", "Providers must inform users."),
    ("Zgodnie z E2 dostawcy muszą informować osoby.", "Dostawcy muszą informować osoby."),
    ("Article 53(1), point (a) applies to providers.", "Article 53(1), point (a) applies to providers."),
])
def test_excerpt_references_are_removed(raw, clean):
    assert strip_excerpt_references(raw) == clean


def test_an_excerpt_id_used_as_a_word_becomes_its_citation():
    excerpts = {"E3": {"act": "DORA", "label": "Article 11(6), point (a)"}}
    assert strip_excerpt_references("E3 requires yearly tests.", excerpts) == \
        "DORA Article 11(6), point (a) requires yearly tests."


def test_verifier_schema_requires_the_five_checks():
    item = verdict_schema(2)["properties"]["verdicts"]["items"]
    assert item["required"] == ["claim", "checks", "support", "note"]
    assert item["properties"]["checks"]["required"] == ["actor", "modality", "conditions", "exceptions", "additions"]


def test_supported_label_with_a_failed_check_is_downgraded():
    ok = dict.fromkeys(["actor", "modality", "conditions", "exceptions", "additions"], "ok")
    verifier = ModelVerifier(FakeOpenAI([completion({"verdicts": [
        {"claim": 1, "checks": ok, "support": "supported", "note": ""},
        {"claim": 2, "checks": {**ok, "modality": "problem"}, "support": "supported", "note": ""}]})]), "judge")
    quote = "Providers shall keep the documentation up to date."
    accepted, rejected, _ = verify_claims([claim("Providers must keep the documentation up to date.", quote),
                                           claim("Providers keep the documentation current.", quote)], verifier)
    assert [c["support"] for c in accepted] == ["supported"]
    assert rejected[0]["support"] == "partial" and rejected[0]["failed_checks"] == ["modality"]
    assert "modality" in rejected[0]["support_note"]
