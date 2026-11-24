# AI guidance integration validation — 24 November 2026

Base: `89d69366d3900c4d818edcd08d320e287ef073a7`. This report describes the accompanying change, not a prior release.
Environment: Linux, Python 3.12; isolated environment installed with `pip install -e '.[dev]'`.
No Azure resources, embedding requests or live model calls were made. No cloud credentials were available.

## Confirmed locally

- 139 automated tests pass; `ruff check .` passes.
- Real official-source import succeeds for all seven source filters, producing 1,645 citable units.
- AI Act: 113 articles / 877 units; DORA: 64 articles / 601 units.
- NIST AI RMF: 48 pages / 48 units; GenAI Profile: 64 pages / 64 units.
- GPAI Transparency: 6 pages / 6 units; Copyright: 6 pages / 6 units; Safety and Security: 43 pages / 43 units.
- `scripts/check_corpus.py` verifies EU structure, registered source presence, PDF page coverage and new-edition hashes.
- FastAPI TestClient: health and four new source-filter requests return HTTP 200; selectors contain all new sources.
  `technical documentation` with the Transparency filter returned insufficient evidence; endpoint success is not a retrieval-quality pass.
- All four new PDFs were fetched from the configured official URLs, checked by SHA-256, parsed, stored and searched.
  PDF bytes are preserved and viewer pages identify citations. Unicode NFKC normalisation makes ligatures searchable.
- New-source download failure leaves the previous active corpus unchanged. Tests cover edition drift, wrong page counts,
  redirects, non-PDF bodies, size limits and source provenance.

Reproduction, from the repository root:

```bash
python -m pip install -e '.[dev]'
python -m pytest
ruff check .
regrag ingest
python scripts/check_corpus.py
regrag eval --retrieval-only --cases eval/pilot.json
regrag eval --retrieval-only --cases eval/ai-guidance.json
```

## Retrieval quality: partial, not complete

The new **development** set has ten answerable questions and two unrelated controls.
Expected viewer pages were read from the official documents. This is not an independent held-out evaluation.
The last command above currently exits **1**, correctly reporting a miss:

- Expected source locator retrieved: **9/10**.
- Expected source locator ranked first: **6/10**.
- Unrelated controls without evidence: **2/2**; this does not establish model abstention quality.
- `GEN01` (definition of confabulation) misses the expected definition on viewer page 10.
  Source-title words and cover/reference pages crowd the top eight lexical results. Normalising PDF ligatures
  is necessary but does not resolve that ranking problem. Do not retune the question or remove the miss to pass the gate.
- The original EU pilot still retrieves the expected article **8/8**, ranked first **8/8**. One of two
  original controls retrieves distractors; generation/abstention for it needs live evaluation.

See [the machine-readable new-source results](ai-guidance-retrieval-2026-11-24.json).
Legacy JSON keys named `expected_article_*` now also score PDF `unit_ids`; Markdown labels say source locator.
A null article is rejected as an expected locator, preventing any NIST page from counting as the right page.

## Remaining completion gates

1. Improve lexical ranking against this development set, preserving the failed baseline, then evaluate new unseen questions.
2. Run generation and verification against the same source-filtered questions using a real configured model.
   Manually review shown and rejected claims, citations, signatory scope, legal force and abstentions.
3. Deploy the updated image, rerun ingest and verify all seven sources in the active versioned Azure index.
4. Repeat source-filtered API/web tests and full evaluation with Azure hybrid retrieval.
5. Verify resource cleanup after the paid session and retain anonymised execution evidence.

Commands for an operator with Azure credentials, after reviewing the normal deployment manual:

```bash
regrag eval --cases eval/ai-guidance.json --output .local/eval-guidance-model
# After deploying this revision and completing Azure ingestion:
REGRAG_BACKEND=azure regrag eval --cases eval/ai-guidance.json --output .local/eval-guidance-azure
```

These commands need the usual endpoint/deployment and Entra configuration. Do not paste secrets into reports.
The importer and API are implemented; the above quality and live-integration gates remain open.
