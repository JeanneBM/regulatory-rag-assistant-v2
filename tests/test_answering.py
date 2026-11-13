import pytest

from conftest import FakeOpenAI, completion, unit
from regrag.generation import GenerationError, Generator, answer_schema
from regrag.pipeline import Assistant
from regrag.retrieval import LocalRetriever
from regrag.verification import ModelVerifier, rule_check, verify_claims

EVIDENCE = [unit(), unit("DORA-art-6-par-5", text="5. The ICT risk management framework shall be "
                         "documented and reviewed at least once a year.", label="Article 6(5)")]


def generator(*replies):
    client = FakeOpenAI(list(replies))
    return Generator(client, "chat"), client


def test_model_selects_excerpts_and_application_copies_full_unit_text():
    gen, client = generator(completion({"claims": [
        {"statement": "Financial entities must have a documented ICT risk management framework.",
         "excerpt_id": "E1"}], "abstention_reason": ""}))
    result = gen.generate("What does DORA say?", EVIDENCE)
    [claim] = result["claims"]
    assert claim["quote"] == EVIDENCE[0]["text"]
    assert claim["citation"] == "DORA Article 6(1)" and claim["unit_id"] == EVIDENCE[0]["id"]
    request = client.requests[0]
    schema = request["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert schema["schema"]["properties"]["claims"]["items"]["properties"]["excerpt_id"]["enum"] == ["E1", "E2"]
    assert request["temperature"] == 0
    assert result["usage"]["total_tokens"] == 120


@pytest.mark.parametrize("payload, error", [
    ({"claims": [{"statement": "x", "excerpt_id": "E9"}], "abstention_reason": ""}, "unknown evidence"),
    ({"claims": [{"statement": "x", "excerpt_id": "E1"}], "abstention_reason": "No."}, "same time"),
    ({"claims": [{"statement": " ", "excerpt_id": "E1"}], "abstention_reason": ""}, "statement"),
    ({"claims": [{"statement": "(E1)", "excerpt_id": "E1"}], "abstention_reason": ""}, "statement"),
    ({"claims": "none"}, "claims list"),
])
def test_invalid_model_output_is_an_error(payload, error):
    gen, _ = generator(completion(payload))
    with pytest.raises(GenerationError, match=error):
        gen.generate("q", EVIDENCE)


def test_claims_over_the_limit_are_dropped_and_counted_not_fatal():
    claims = [{"statement": f"Statement number {i}.", "excerpt_id": "E1"} for i in range(1, 7)]
    gen, _ = generator(completion({"claims": claims, "abstention_reason": ""}))
    result = gen.generate("q", EVIDENCE)
    assert [c["statement"] for c in result["claims"]] == [f"Statement number {i}." for i in range(1, 5)]
    assert result["claims_dropped"] == 2


def test_excerpt_ids_never_reach_the_statement():
    gen, _ = generator(completion({"claims": [
        {"statement": "The framework is reviewed at least once a year (E2).", "excerpt_id": "E2"}],
        "abstention_reason": ""}))
    [claim] = gen.generate("q", EVIDENCE)["claims"]
    assert claim["statement"] == "The framework is reviewed at least once a year."


@pytest.mark.parametrize("reply, error", [
    (completion('{"claims": [', finish_reason="length"), "length"),
    (completion(None, finish_reason="content_filter"), "content_filter"),
    (completion(None, refusal="I cannot help with that."), "refused"),
    (completion("not json"), "valid JSON"),
])
def test_truncated_filtered_or_refused_replies_are_errors(reply, error):
    gen, _ = generator(reply)
    with pytest.raises(GenerationError, match=error):
        gen.generate("q", EVIDENCE)


def test_answer_schema_has_no_unsupported_strict_keywords():
    text = str(answer_schema(["E1"]))
    for keyword in ("maxItems", "minLength", "pattern"):
        assert keyword not in text


def claim(statement, quote=EVIDENCE[1]["text"], label="Article 6(5)"):
    return {"statement": statement, "quote": quote, "label": label, "article": "6", "act": "DORA",
            "citation": f"DORA {label}", "unit_id": "DORA-art-6-par-5", "url": ""}


def test_rule_check_flags_invented_figures_and_article_references():
    assert rule_check(claim("The framework is reviewed at least once a year.")) is None
    assert rule_check(claim("Under Regulation (EU) 2022/2554, Article 6(5) requires annual review.")) is None
    verdict = rule_check(claim("The framework must be reviewed within 72 hours."))
    assert verdict["support"] == "unsupported" and "72" in verdict["note"]
    verdict = rule_check(claim("Article 11(3) also requires a yearly review of the framework."))
    assert verdict["support"] == "partial" and "11" in verdict["note"]
    assert rule_check(claim("Zgodnie z art. 6 ust. 5 ramy przegląda się co najmniej raz w roku.")) is None
    assert rule_check(claim("Art. 17 wymaga corocznego przeglądu ram."))["support"] == "partial"


def test_strict_policy_returns_only_supported_claims():
    verifier = ModelVerifier(FakeOpenAI([completion({"verdicts": [
        {"claim": 1, "support": "supported", "note": ""},
        {"claim": 2, "support": "partial", "note": "Drops the qualifier 'at least'."}]})]), "judge")
    claims = [claim("The framework is reviewed at least once a year."),
              claim("The framework is reviewed once a year.")]
    accepted, rejected, usage = verify_claims(claims, verifier, "strict")
    assert [c["support"] for c in accepted] == ["supported"]
    assert rejected[0]["support"] == "partial" and "at least" in rejected[0]["support_note"]
    assert usage["total_tokens"] == 120
    lenient = verify_claims(claims, ModelVerifier(FakeOpenAI([completion({"verdicts": [
        {"claim": 1, "support": "supported", "note": ""},
        {"claim": 2, "support": "partial", "note": "x"}]})]), "judge"), "lenient")
    assert len(lenient[0]) == 2


def test_verifier_must_return_one_verdict_per_claim():
    verifier = ModelVerifier(FakeOpenAI([completion({"verdicts": [
        {"claim": 1, "support": "supported", "note": ""}]})]), "judge")
    with pytest.raises(ValueError, match="exactly one verdict"):
        verifier.verify([claim("a statement"), claim("another statement")])


def assistant(*replies, verify=True):
    client = FakeOpenAI(list(replies))
    return Assistant(LocalRetriever(EVIDENCE), Generator(client, "chat"),
                     ModelVerifier(client, "judge") if verify else None), client


def test_pipeline_answers_with_verified_claims_and_sums_usage():
    bot, client = assistant(
        completion({"claims": [{"statement": "The framework is reviewed at least once a year.",
                                "excerpt_id": "E1"}], "abstention_reason": ""}),
        completion({"verdicts": [{"claim": 1, "support": "supported", "note": ""}]}))
    result = bot.ask("How often is the ICT risk management framework reviewed?")
    assert result["status"] == "answered"
    assert result["claims"][0]["support"] == "supported"
    assert result["usage"]["total_tokens"] == 240
    assert len(client.requests) == 2


def test_pipeline_abstains_when_every_claim_fails_verification():
    bot, _ = assistant(
        completion({"claims": [{"statement": "Reviews happen within 72 hours.", "excerpt_id": "E1"}],
                    "abstention_reason": ""}))
    result = bot.ask("How often is the ICT risk management framework reviewed?")
    assert result["status"] == "insufficient_evidence"
    assert result["claims"] == [] and result["rejected_claims"][0]["support_method"] == "rule"


def test_pipeline_never_calls_the_model_without_evidence():
    bot, client = assistant()
    result = bot.ask("How do I bake a chocolate cake?")
    assert result["status"] == "insufficient_evidence" and client.requests == []


def test_pipeline_reports_model_abstention_and_retrieval_only_mode():
    bot, _ = assistant(completion({"claims": [], "abstention_reason": "No VAT rate in the excerpts."}))
    result = bot.ask("What VAT rate applies to the ICT risk management framework?")
    assert result["status"] == "insufficient_evidence"
    assert result["abstention_reason"] == "No VAT rate in the excerpts."
    evidence_only = Assistant(LocalRetriever(EVIDENCE)).ask("ICT risk management framework")
    assert evidence_only["status"] == "retrieval_only" and evidence_only["evidence"]
