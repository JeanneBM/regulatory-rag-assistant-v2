import json
from pathlib import Path

from conftest import FakeOpenAI, completion, unit
from regrag.evaluation import load_cases, run
from regrag.generation import Generator
from regrag.pipeline import Assistant
from regrag.retrieval import LocalRetriever
from regrag.verification import ModelVerifier

CASES = [
    {"id": "D02", "question": "What does DORA say about the ICT risk management framework?",
     "expected": {"act": "DORA", "article": "6"}},
    {"id": "N01", "question": "How do I bake a chocolate cake?", "expected": None},
]


def test_pilot_cases_file_is_valid():
    cases = load_cases(Path(__file__).resolve().parents[1] / "eval" / "pilot.json")
    assert len(cases) == 10
    assert sum(1 for c in cases if c["expected"]) == 8


def test_retrieval_only_run_reports_hits_and_writes_files(tmp_path):
    report, code = run(Assistant(LocalRetriever([unit()])), CASES, True, tmp_path, log=lambda _: None)
    assert code == 0
    assert report["summary"]["checks"] == {"retrieval_hit": 1, "no_evidence": 1}
    assert report["summary"]["expected_article_retrieved"] == "1/1"
    assert report["summary"]["expected_article_ranked_first"] == "1/1"
    assert report["summary"]["correct_abstentions"] == "n/a"
    saved = json.loads(Path(report["files"][0]).read_text())
    assert saved["cases"][0]["retrieved"] == ["DORA-art-6-par-1"]
    assert "Manual review" in Path(report["files"][1]).read_text()


def test_full_run_separates_citation_abstention_support_and_verification_effect(tmp_path):
    client = FakeOpenAI([
        completion({"claims": [
            {"statement": "Financial entities need a documented ICT risk management framework within "
                          "their overall risk management system.", "excerpt_id": "E1"},
            {"statement": "Every financial entity must use the same framework.", "excerpt_id": "E1"}],
            "abstention_reason": ""}),
        completion({"verdicts": [{"claim": 1, "support": "supported", "note": ""},
                                 {"claim": 2, "support": "partial", "note": "Overgeneralises."}]}),
    ])
    bot = Assistant(LocalRetriever([unit()]), Generator(client, "chat"), ModelVerifier(client, "judge"))
    report, code = run(bot, CASES, False, tmp_path, log=lambda _: None)
    summary = report["summary"]
    assert code == 0
    assert summary["checks"] == {"citation_hit_needs_review": 1, "abstained": 1}
    assert summary["expected_article_cited"] == "1/1" and summary["correct_abstentions"] == "1/1"
    assert summary["claim_support_labels"] == {"supported": 1, "partial": 1}
    assert summary["verification"] == {
        "claims_generated": 2, "claims_shown": 1, "rejected_by_rules": 0, "rejected_by_model": 1,
        "expected_article_cited_before": "1/1", "expected_article_cited_after": "1/1"}
    assert summary["tokens"]["total_tokens"] == 240
    rejected = report["cases"][0]["rejected_claims"][0]
    assert rejected["quote"] == unit()["text"] and rejected["support_method"] == "model"
    table = Path(report["files"][1]).read_text()
    row = "| D02 | DORA Article 6(1) | Every financial entity must use the same framework. | partial (model) | no |"
    assert row in table


def test_misses_and_errors_fail_the_run(tmp_path):
    class Broken(Assistant):
        def ask(self, question, act=None):
            raise RuntimeError("boom")
    _, code = run(Broken(LocalRetriever([unit()])), CASES, False, tmp_path, log=lambda _: None)
    assert code == 1
    _, code = run(Assistant(LocalRetriever([unit(text="Unrelated provision about market surveillance "
                                                 "authorities and their powers.", title="Market surveillance")])),
                  CASES[:1], True, tmp_path, log=lambda _: None)
    assert code == 1
