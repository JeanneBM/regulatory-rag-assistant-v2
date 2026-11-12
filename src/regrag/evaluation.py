"""Pilot evaluation: retrieval, citation, abstention, claim support, tokens, latency.

Automatic checks separate three questions the pilot showed must not be conflated:
did retrieval find the expected article, did the answer cite it, and does each
statement follow from its quotation. The verifier labels answer the third only
provisionally; the Markdown report contains a manual-review column for that reason.
"""
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

FAILURES = {"retrieval_miss", "expected_answer_missing", "expected_abstention_missing", "error"}


def load_cases(path: Path) -> list[dict]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    for case in cases:
        if not {"id", "question"} <= set(case):
            raise ValueError(f"Invalid case: {case}")
    return cases


def _expected(case: dict) -> tuple[str, str] | None:
    expected = case.get("expected")
    return (expected["act"], str(expected["article"])) if expected else None


def run_case(assistant, case: dict, retrieval_only: bool) -> dict:
    expected = _expected(case)
    row = {"id": case["id"], "question": case["question"],
           "expected": {"act": expected[0], "article": expected[1]} if expected else None}
    start = perf_counter()
    try:
        if retrieval_only:
            evidence = assistant.retriever.retrieve(case["question"], case.get("act"))
            result = {"status": "retrieval_only", "evidence": evidence, "claims": [],
                      "rejected_claims": [], "usage": {}}
        else:
            result = assistant.ask(case["question"], case.get("act"))
    except Exception as exc:
        row.update(check="error", error_type=type(exc).__name__, error=str(exc)[:300],
                   elapsed_ms=round((perf_counter() - start) * 1000))
        return row
    retrieved = [(e["act"], str(e["article"])) for e in result["evidence"]]
    row.update(
        status=result["status"],
        retrieved=[e["id"] for e in result["evidence"]],
        expected_retrieved=(expected in retrieved) if expected else None,
        expected_rank=(retrieved.index(expected) + 1) if expected in retrieved else None,
        claims=[{"citation": c["citation"], "statement": c["statement"], "support": c["support"],
                 "support_note": c["support_note"], "quote": c["quote"]} for c in result["claims"]],
        rejected_claims=[{"citation": c["citation"], "statement": c["statement"],
                          "support": c["support"], "support_note": c["support_note"]}
                         for c in result["rejected_claims"]],
        usage=result.get("usage", {}),
    )
    if retrieval_only:
        if expected:
            row["check"] = "retrieval_hit" if row["expected_retrieved"] else "retrieval_miss"
        else:
            row["check"] = "distractors_retrieved" if retrieved else "no_evidence"
    elif expected:
        cited = any((c["act"], str(c["article"])) == expected for c in result["claims"])
        row["check"] = ("citation_hit_needs_review" if result["status"] == "answered" and cited
                        else "expected_answer_missing")
    else:
        row["check"] = ("abstained" if result["status"] == "insufficient_evidence"
                        and not result["claims"] else "expected_abstention_missing")
    row["elapsed_ms"] = round((perf_counter() - start) * 1000)
    return row


def summarise(rows: list[dict], retrieval_only: bool = False) -> dict:
    answerable = [r for r in rows if r["expected"]]
    controls = [r for r in rows if not r["expected"]]
    support = Counter(c["support"] for r in rows for c in r.get("claims", []) + r.get("rejected_claims", []))
    latencies = sorted(r["elapsed_ms"] for r in rows)
    tokens = Counter()
    for r in rows:
        tokens.update(r.get("usage") or {})
    cited = sum(r["check"] == "citation_hit_needs_review" for r in answerable)
    abstained = sum(r["check"] == "abstained" for r in controls)
    return {
        "checks": dict(Counter(r["check"] for r in rows)),
        "expected_article_retrieved": f"{sum(bool(r.get('expected_retrieved')) for r in answerable)}/{len(answerable)}",
        "expected_article_ranked_first": f"{sum(r.get('expected_rank') == 1 for r in answerable)}/{len(answerable)}",
        # Citation and abstention need generation; retrieval-only runs cannot measure them.
        "expected_article_cited": "n/a" if retrieval_only else f"{cited}/{len(answerable)}",
        "correct_abstentions": "n/a" if retrieval_only else f"{abstained}/{len(controls)}",
        "controls_without_evidence": f"{sum(r['check'] == 'no_evidence' for r in controls)}/{len(controls)}",
        "claim_support_labels": dict(support),
        "tokens": dict(tokens),
        "latency_ms": {"p50": statistics.median(latencies) if latencies else None,
                       "max": latencies[-1] if latencies else None},
    }


def markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"# Pilot run {report['utc'][:10]} ({report['mode']}, {report['backend']})", "",
        "| Check | Result |", "| --- | --- |",
        f"| Expected article retrieved | {s['expected_article_retrieved']} |",
        f"| Expected article ranked first | {s['expected_article_ranked_first']} |",
        f"| Expected article cited | {s['expected_article_cited']} |",
        f"| Correct abstentions | {s['correct_abstentions']} |",
        f"| Verifier labels | {s['claim_support_labels']} |",
        f"| Tokens | {s['tokens']} |", "",
        "Verifier labels are model judgements. Fill in the manual column before counting a "
        "claim as supported.", "",
        "| Case | Citation | Statement | Verifier | Manual review |", "| --- | --- | --- | --- | --- |",
    ]
    for row in report["cases"]:
        claims = row.get("claims", []) + row.get("rejected_claims", [])
        if not claims:
            lines.append(f"| {row['id']} | - | {row['check']} | - | |")
        for claim in claims:
            statement = claim["statement"].replace("|", "\\|")
            lines.append(f"| {row['id']} | {claim['citation']} | {statement} | {claim['support']} | |")
    return "\n".join(lines) + "\n"


def run(assistant, cases: list[dict], retrieval_only: bool, output_dir: Path, log=print) -> tuple[dict, int]:
    rows = []
    for case in cases:
        row = run_case(assistant, case, retrieval_only)
        rows.append(row)
        log(f"{row['id']}: {row['check']}")
    now = datetime.now(UTC)
    report = {"utc": now.isoformat(), "mode": "retrieval_only" if retrieval_only else "full",
              "backend": assistant.retriever.name,
              "corpus_sha256": (assistant.manifest or {}).get("corpus_sha256"),
              "summary": summarise(rows, retrieval_only), "cases": rows}
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"eval-{now:%Y%m%dT%H%M%SZ}"
    (output_dir / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / f"{stem}.md").write_text(markdown(report), encoding="utf-8")
    report["files"] = [str(output_dir / f"{stem}.json"), str(output_dir / f"{stem}.md")]
    failed = FAILURES & set(report["summary"]["checks"])
    return report, int(bool(failed))
