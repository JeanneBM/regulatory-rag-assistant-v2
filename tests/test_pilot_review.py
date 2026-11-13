"""Replay the deterministic verification rules on the 26 manually reviewed pilot claims.

The rules were written after this review, so this checks that they do what was
intended on these claims (no correct claim rejected, the known errors caught), not
how well they generalise. New pilot questions are needed for that.
"""
import json
import re
from pathlib import Path

import pytest

from regrag.generation import strip_excerpt_references
from regrag.verification import rule_check

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
RUN = json.loads((EVIDENCE / "eval-20261113T115349Z.json").read_text(encoding="utf-8"))
REVIEW = json.loads((EVIDENCE / "eval-20261113T115349Z-review.json").read_text(encoding="utf-8"))
ACTS = {"DORA": "DORA", "AI Act": "AI_ACT"}


def recorded_claims():
    labels = {(i["case"], i["shown"], i["index"]): i for i in REVIEW["items"]}
    for case in RUN["cases"]:
        for shown, key in ((True, "claims"), (False, "rejected_claims")):
            for index, claim in enumerate(case.get(key) or []):
                act, label, article = re.match(r"(DORA|AI Act) (Article (\d+).*)", claim["citation"]).groups()
                replayable = {"statement": strip_excerpt_references(claim["statement"]), "quote": claim["quote"],
                              "act": ACTS[act], "label": label, "article": article, "citation": claim["citation"]}
                yield labels[(case["id"], shown, index)], replayable


CLAIMS = list(recorded_claims())


def test_every_recorded_claim_has_a_manual_label():
    assert len(CLAIMS) == len(REVIEW["items"]) == 26


def test_recorded_statements_lose_their_excerpt_ids():
    for _, claim in CLAIMS:
        assert not re.search(r"\bE\d+\b", claim["statement"])


@pytest.mark.parametrize("review, claim", [c for c in CLAIMS if c[0]["manual"] == "supported"],
                         ids=lambda v: v.get("citation", "") if isinstance(v, dict) else "")
def test_rules_never_reject_a_claim_reviewed_as_supported(review, claim):
    assert rule_check(claim) is None


@pytest.mark.parametrize("citation, note", [
    ("AI Act Article 4", "to their best extent"),
    ("AI Act Article 66, point (f)", "grants a power"),
    ("AI Act Article 5(1), point (c)", "does not contain"),
    ("AI Act Article 6(3)", "Annex III"),
    ("AI Act Article 50(3)", "omits an exception"),
])
def test_rules_catch_the_reviewed_errors_they_target(citation, note):
    [(review, claim)] = [c for c in CLAIMS if c[0]["citation"] == citation]
    assert review["manual"] in {"partial", "wrong"}
    verdict = rule_check(claim)
    assert verdict["support"] == "partial" and note in verdict["note"]


def test_no_rule_fires_on_figures_any_more():
    for _, claim in CLAIMS:
        verdict = rule_check(claim)
        assert not verdict or "figures" not in verdict["note"]
