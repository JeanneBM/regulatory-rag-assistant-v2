# Final validation session (Windows Git Bash)

The local checks and the Azure checks are separate. Keep all reports, including failures.
This session validates the seven-source revision; the older two-source Azure smoke
is not evidence for the NIST/GPAI additions. No new corpus features are planned in this session.

**25 November session checkpoint:** both full Azure sets are complete and all
62 statements have been source-reviewed: 22 cases, retrieval/citations 18/18,
abstentions 4/4, zero technical errors. [Combined findings](../evidence/azure-full-evaluation-2026-11-25.md)
record 46 supported, 11 partial and one wrong shown statement. Coverage is evaluated;
strict semantic fidelity remains a measured limitation.

The later reference-qualifier correction passed 158 offline tests and then its
[SCOPE01 Azure regression](../evidence/reference-scope-azure-2026-11-25.md): exact unit
first and cited 1/1, both shown assertions supported by the quote, zero errors.
The original full-set semantic findings remain unchanged.

After reported deployment completion, the [final UI smoke](../evidence/azure-final-web-smoke-2026-11-25.md)
passed in two user screenshots: cited Article 54(3)(a) answer and retrieval-gated
abstention with no previous answer cards visible. Both used All sources. This is
visual functional evidence; a deployment image digest was not captured.

Only cleanup confirmation remains for the dedicated lab. After saving the UI results:

```bash
azd down --purge &&
az group exists --name '<RECORDED_GROUP>'
```

The final resource-group result should be `false`. It has not yet been supplied.
The original semantic findings remain recorded; no more model runs are needed for
this session's validation record.

## 1. Prepare the checkout

For a new checkout:

```bash
cd ~
git clone https://github.com/JeanneBM/regulatory-rag-assistant-v2.git
cd regulatory-rag-assistant-v2
```

For an existing clean checkout, enter its directory and run `git pull --ff-only`.
Then:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e '.[dev]'
python -m pytest
ruff check src tests scripts
node scripts/test-web-ui.cjs
```

Node is required only for the UI regression check. The application is Python.
Run individual commands and stop on unexpected failures.

## 2. Check the source corpus without Azure

```bash
regrag ingest
python scripts/check_corpus.py
regrag eval --retrieval-only --cases eval/pilot.json --output .local/final-eu-retrieval
regrag eval --retrieval-only --cases eval/ai-guidance.json --output .local/final-guidance-retrieval
```

The recorded guidance baseline is 9/10 expected source locators retrieved and
6/10 ranked first. GEN01 fails; its nonzero exit is an actual quality miss, not an
installation error. Preserve that baseline and compare any later results against it.
Do not remove the case, change its expected page or lower thresholds just to pass.
The EU baseline retrieves the expected article 8/8. A control can retrieve distractors;
only full model evaluation can establish whether the assistant abstains.

## 3. Authenticate and select the Azure route

Reuse the authenticated session and selected azd environment when they already work.
For a new session, authenticate with `az login --use-device-code` and select the
intended subscription before deploying. Do not send access tokens or keys in chat
or commit them.

- **Existing deployment:** use its original azd environment and recorded resource group;
  verify ownership before changing or deleting it. Deploy this revision with `azd deploy`
  and confirm that the postdeploy ingest execution succeeds.
- **Deleted environment:** follow the [deployment manual](../evidence/web-validation-manual.md)
  and README to create a dedicated disposable environment with `azd up`. This creates
  billable resources; use the documented IP allowlist and remove resources after the session.

Do not assume a prior endpoint or local azd configuration still exists. An ingest error
or incomplete deployment blocks the following checks.

## 4. Load the recorded deployment configuration

From the selected, successfully deployed azd environment:

```bash
azd env get-values | tr -d '\r' > .env.azure
set -a
source .env.azure
set +a
curl -fsS "$WEB_URL/healthz"
curl -fsS "$WEB_URL/readyz"
curl -fsS "$WEB_URL/api/info"
```

Keep `.env.azure` private. The info response must list AI_ACT, DORA, NIST_AI_RMF,
NIST_GENAI, GPAI_TRANSPARENCY, GPAI_COPYRIGHT and GPAI_SAFETY_SECURITY, with generation
and model verification enabled. A health response alone does not prove indexing.

## 5. Run full evaluation and review the answers

```bash
REGRAG_BACKEND=azure regrag eval --cases eval/pilot.json --output .local/final-azure-eu
REGRAG_BACKEND=azure regrag eval --cases eval/ai-guidance.json --output .local/final-azure-guidance
```

Open the JSON reports for full quotations and use the Markdown tables as a checklist.
For every shown and rejected claim, review its quotation,
conditions, exceptions, signatory scope and legal force. A correct citation is not proof
that the claim follows from it. Check both controls; errors are not abstentions.
Record usage, latency, model/deployment names, the tested commit and the result.
The development set does not establish held-out quality.

Open `$WEB_URL` and try a question from each source filter. Confirm source-page links,
then submit an unrelated question and a failing request: previous evidence must disappear.
Preserve anonymised results and avoid publishing operator credentials or raw environment files.

## 6. Cleanup and final status

For the dedicated disposable environment created for this test:

```bash
azd down --purge
```

Check the recorded resource group is absent with `az group exists --name '<RECORDED_GROUP>'`.
Do not delete unrelated or shared resource groups. Save cleanup evidence even if a test fails.
Only then update README with the actual outcome: validated, failed, or stopped at a named gate.
Do not label this revision fully Azure-validated before these checks have run.
