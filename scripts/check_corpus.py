"""Structural checks on the real imported corpus, run by the live-ingest workflow.

Fails when the Official Journal layout drifts in ways the parser would silently
mis-handle, and reports key statistics as GitHub annotations and a job summary.
"""
import json
import os
import re
import sys
from pathlib import Path

from regrag.parser import corpus_stats
from regrag.sources import ACTS
from regrag.storage import LocalCorpusStore

HEADING = re.compile(r"^(CHAPTER|SECTION)\s+[IVXLC\d]+$", re.MULTILINE)


def notice(message: str) -> None:
    print(f"::notice title=corpus::{message}".replace("\n", "%0A"))


def main() -> int:
    active = LocalCorpusStore(Path(os.getenv("REGRAG_LOCAL_DIR") or ".local")).active()
    if not active:
        print("No local corpus; run `python -m regrag ingest` first", file=sys.stderr)
        return 1
    manifest, units = active
    stats = corpus_stats(units)
    by_label = {(u["act"], u["label"]): u for u in units}
    failures = []

    for key, act in ACTS.items():
        entry = stats.get(key)
        if not entry or entry["articles"] != act.articles:
            failures.append(f"{key}: expected {act.articles} articles, found {entry and entry['articles']}")
            continue
        notice(f"{key}: {json.dumps(entry)}")
        if entry["with_point"] == 0:
            failures.append(f"{key}: no point-level units; table layout not recognised")
        if entry["with_title"] < 0.9 * entry["units"]:
            failures.append(f"{key}: article titles missing for many units")
    for unit in units:
        if HEADING.search(unit["text"]):
            failures.append(f"{unit['id']}: contains a chapter or section heading")
            break

    social_scoring = by_label.get(("AI_ACT", "Article 5(1), point (c)"))
    if not social_scoring or not re.search(r"^\(i\) ", social_scoring["text"], re.MULTILINE) \
            or not re.search(r"^\(ii\) ", social_scoring["text"], re.MULTILINE):
        failures.append("AI Act Article 5(1), point (c) should carry sub-points (i) and (ii)")
    else:
        notice("AI Act Art. 5(1)(c): " + social_scoring["text"][:900])
    definitions = [u for u in units if u["act"] == "AI_ACT" and u["article"] == "3" and u["point"]]
    if len(definitions) < 60:
        failures.append(f"AI Act Article 3 should have about 68 definition points, found {len(definitions)}")
    for label in [("DORA", "Article 6(1)"), ("DORA", "Article 17(1)"), ("AI_ACT", "Article 50(1)")]:
        if label not in by_label:
            failures.append(f"Missing citable unit {label}")
    shapes = {
        "unmarked_rows": sum("-pt-row" in u["id"] for u in units),
        "text_after_points": sum("-text-" in u["id"] for u in units),
        "split_parts": sum("-part-" in u["id"] for u in units),
        "duplicate_markers": sum("-dup" in u["id"] for u in units),
    }
    unusual = [u for u in units if "-pt-row" in u["id"] or "-dup" in u["id"]]
    notice(f"unit shapes: {json.dumps(shapes)}; unusual: "
           + " | ".join(f"{u['id']}: {u['text'][:160]}" for u in unusual[:6]))
    longest = max(units, key=lambda u: len(u["text"]))
    notice(f"corpus {manifest['corpus_sha256'][:12]}: {len(units)} units; longest {longest['id']} "
           f"({len(longest['text'])} chars); sample ids: "
           + ", ".join(u["id"] for u in units[100:106]))

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("| Act | Articles | Units | With paragraph | With point | Anchored |\n|---|---|---|---|---|---|\n")
            for key, entry in stats.items():
                out.write(f"| {key} | {entry['articles']} | {entry['units']} | {entry['with_paragraph']} | "
                          f"{entry['with_point']} | {entry['anchored']} |\n")
    for failure in failures:
        print(f"::error title=corpus::{failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
