# Regulatory RAG Assistant v2

[![CI](https://github.com/JeanneBM/regulatory-rag-assistant-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/JeanneBM/regulatory-rag-assistant-v2/actions/workflows/ci.yml)

A command-line RAG pilot over the EU AI Act and DORA. It imports official English
texts from the EU Publications Office, retrieves passages, and checks whether
each generated statement is supported by its citation. The corpus covers the
original published acts and is intended for research.

## Run locally

From the repository root, with Python 3.11 or newer:

```bash
python -m pip install -e ".[local]"
python -m regrag ingest
python -m regrag ask "What does DORA say about ICT risk management?" --act DORA
python -m regrag eval --retrieval-only
```

The local backend uses TF-IDF and returns passages. It can download the corpus on
first use. Raw documents, the parsed corpus and the evaluation reports are saved
under `.local/`. The default evaluation uses [ten questions](eval/pilot.json)
and writes JSON and Markdown to `.local/eval/`.

## Generate and evaluate answers

With an existing Azure OpenAI deployment, run `az login` and set
`AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_CHAT_DEPLOYMENT`. The same commands
can then generate answers with local retrieval. Run `python -m regrag eval`
without `--retrieval-only` to measure retrieval, citations, abstentions and
claim verification.

To test hybrid retrieval, use existing Azure AI Search, Azure OpenAI and Blob
Storage resources. Set the Search, embedding and storage variables in
[.env.example](.env.example) in your shell, then run:

```bash
python -m regrag ingest --target azure
REGRAG_BACKEND=azure python -m regrag eval
```

The import identity needs write access to the configured storage container and
Search indexes. The query identity needs read access. The import verifies the
document count before switching the Search alias and preserves the previous
index for rollback. These commands use existing resources.

## What the pilot measures

- Passages are split at article, paragraph and point boundaries. The application
  attaches the exact source passage and its EUR-Lex link.
- Deterministic checks validate figures and article references. A model
  verifier checks whether the cited passage supports the full statement,
  including conditions and exceptions. With verification enabled, strict mode
  shows only supported claims.
- The evaluation compares citations before and after verification on the same
  generated claims. Review accepted and rejected claims manually to check for
  both unsupported statements and correct statements discarded by the verifier.
- The [pre-deployment report](evidence/azure-stack-validation-2026-11-12.md)
  records the original import and local retrieval results. Azure answer quality
  still needs an end-to-end run.

CI runs the offline tests and audits the runtime lock. The live-import workflow
checks the official corpus and local retrieval when relevant files change or
when run manually.
