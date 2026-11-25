"""Synthetic PDF examples: page scope, voluntary status and strict model filtering."""
import json

import pytest

from conftest import FakeOpenAI, completion
from regrag.sources import all_sources
from regrag.verification import CHECKS, ModelVerifier, rule_check, verify_claims


def pdf_claim(statement, quote, act="GPAI_TRANSPARENCY"):
    return {"statement": statement, "quote": quote, "act": act, "article": None,
            "label": "PDF page 1, part 1", "citation": "Fixture PDF page 1, part 1"}


@pytest.mark.parametrize("statement,quote", [
    ("Governance requires continual attention.", "Effective governance requires continual attention."),
    ("Effective risk management requires organisational commitment.",
     "Effective risk management requires organisational commitment."),
])
@pytest.mark.parametrize("act", ["NIST_AI_RMF", "NIST_GENAI"])
def test_descriptive_prerequisites_in_voluntary_guidance_reach_the_model(statement, quote, act):
    assert rule_check(pdf_claim(statement, quote, act)) is None


@pytest.mark.parametrize("quote", [
    "Measure A: Signatories publish contact details. Measure B: Complaints are considered unless unfounded.",
    "Measure A: Signatories publish contact details. Measure B: Mitigations are updated as appropriate.",
    "Measure A: Signatories publish contact details. Measure B: A protocol named Exclusion is described.",
])
def test_a_page_wide_keyword_does_not_reject_an_unrelated_action(quote):
    assert rule_check(pdf_claim("Signatories publish contact details.", quote)) is None


def test_real_pdf_exemptions_are_still_checked_by_the_model_using_the_full_page():
    claim = pdf_claim("Signatories publish documentation.",
                      "This measure exempts qualifying models. Signatories publish documentation.")
    checks = {**dict.fromkeys(CHECKS, "ok"), "exceptions": "problem"}
    client = FakeOpenAI([completion({"verdicts": [
        {"claim": 1, "checks": checks, "support": "partial", "note": "Drops the exemption."},
    ]})])
    accepted, rejected, _ = verify_claims([claim], ModelVerifier(client, "judge"))
    assert not accepted and rejected[0]["support_method"] == "model"
    item = json.loads(client.requests[0]["messages"][1]["content"])["items"][0]
    assert item["evidence"] == f"{claim['citation']}\n{claim['quote']}"
    assert item["source_type"] == "voluntary_code"
    assert item["version"] == all_sources()[claim["act"]].version


def test_recipient_duties_cannot_pass_when_an_actor_check_fails():
    claim = pdf_claim("Providers ensure that recipients protect information.",
                      "Recipients protect information.")
    checks = {**dict.fromkeys(CHECKS, "ok"), "actor": "problem"}
    client = FakeOpenAI([completion({"verdicts": [
        {"claim": 1, "checks": checks, "support": "supported", "note": "The duty is on recipients."},
    ]})])
    accepted, rejected, _ = verify_claims([claim], ModelVerifier(client, "judge"))
    assert not accepted
    assert rejected[0]["support"] == "partial" and rejected[0]["failed_checks"] == ["actor"]


def test_registered_source_context_takes_precedence_over_claim_metadata():
    claim = {**pdf_claim("Governance requires attention.", "Governance requires attention.", "NIST_AI_RMF"),
             "source_type": "eu_regulation", "version": "wrong"}
    client = FakeOpenAI([completion({"verdicts": [
        {"claim": 1, "checks": dict.fromkeys(CHECKS, "ok"), "support": "supported", "note": ""},
    ]})])
    accepted, rejected, _ = verify_claims([claim], ModelVerifier(client, "judge"))
    assert accepted and not rejected
    item = json.loads(client.requests[0]["messages"][1]["content"])["items"][0]
    assert item["source_type"] == "voluntary_framework"
    assert item["version"] == all_sources()["NIST_AI_RMF"].version


def test_pdf_numeric_rule_still_runs_before_model_verification():
    claim = pdf_claim("Signatories respond within 99 days.", "Signatories respond within 7 days.")
    accepted, rejected, _ = verify_claims([claim], ModelVerifier(FakeOpenAI(), "judge"))
    assert not accepted
    assert rejected[0]["support"] == "unsupported" and rejected[0]["support_method"] == "rule"
    assert "99" in rejected[0]["support_note"]
