"""Automatic import of the acts: download, parse, validate, store, index.

Nothing is downloaded by hand. Any HTTP error, foreign redirect, unexpected content
type, missing article or indexing failure stops the import before the active corpus
or the search alias change.
"""
import hashlib
import json
from datetime import UTC, datetime

from regrag.cellar import fetch_act
from regrag.parser import PARSER_VERSION, parse_act, require_coverage
from regrag.sources import ACTS, Act


def corpus_digest(units: list[dict]) -> str:
    canonical = json.dumps(units, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_corpus(acts: list[Act] | None = None, fetch=fetch_act, now: datetime | None = None):
    acts = list(ACTS.values()) if acts is None else acts
    now = now or datetime.now(UTC)
    units, documents, summary = [], [], {}
    for act in acts:
        document = fetch(act)
        parsed = parse_act(document.html, act)
        require_coverage(parsed, act)
        for unit in parsed:
            unit.update(source_sha256=document.sha256, fetched_from=document.fetched_from,
                        language="EN", version="original published act")
        units.extend(parsed)
        documents.append(document)
        summary[act.key] = {
            "celex": act.celex, "title": act.title, "articles": act.articles,
            "units": len(parsed), "eurlex_url": act.eurlex_url,
            "fetched_from": document.fetched_from, "source_sha256": document.sha256,
        }
    manifest = {
        "corpus_sha256": corpus_digest(units),
        "parser_version": PARSER_VERSION,
        "fetched_at": now.isoformat(),
        "units": len(units),
        "acts": summary,
        "note": "Original published acts, not consolidated versions.",
    }
    return manifest, units, documents


def run_ingest(store, publisher=None, fetch=fetch_act, acts: list[Act] | None = None,
               log=print) -> dict:
    manifest, units, documents = build_corpus(acts, fetch)
    for document in documents:
        manifest["acts"][document.act.key]["raw_uri"] = store.save_raw(
            document.act.celex, document.sha256, document.html)
    store.save_corpus(manifest, units)
    log(f"Parsed {len(units)} citable units; corpus {manifest['corpus_sha256'][:12]}")
    if publisher is not None:
        manifest["search"] = publisher.publish(units, manifest["corpus_sha256"])
    store.activate(manifest)
    return manifest


def ensure_local_corpus(store, fetch=fetch_act, log=print) -> tuple[dict, list[dict]]:
    """Return the local corpus, importing it on first use or when ACTS gained an act."""
    current = store.active()
    if current and set(ACTS) <= set(current[0]["acts"]):
        manifest, units = current
        return manifest, [u for u in units if u["act"] in ACTS]
    log("Importing the acts from the EU Publications Office (first use)")
    run_ingest(store, fetch=fetch, log=log)
    return store.active()
