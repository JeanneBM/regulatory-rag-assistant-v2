# Full seven-source Azure evaluation — 25 November 2026

**Both full development sets were executed and source-reviewed: 22 cases across
all seven sources. Retrieval, citation and abstention checks pass; strict semantic
answer fidelity does not.** Remaining model errors are recorded below rather
than counted as successful answers on the strength of a model label.

The EU run finished at 18:23 UTC and guidance at 18:26 UTC. Both used real hybrid
Azure AI Search, Azure OpenAI generation and model verification under strict policy,
with the same corpus digest. Raw operator reports and all statement/quote reviews
remain private. This public summary contains no deployment identifiers or raw payloads.

| Automatic metric | EU | Guidance | Combined |
| --- | --- | --- | --- |
| Cases | 10 | 12 | 22 |
| Expected source retrieved | 8/8 | 10/10 | 18/18 |
| Expected source ranked first | 8/8 | 10/10 | 18/18 |
| Expected source cited after verification | 8/8 | 10/10 | 18/18 |
| Correct abstentions | 2/2 | 2/2 | 4/4 |
| Controls without retrieved evidence | 1/2 | 2/2 | 3/4 |
| Technical errors | 0 | 0 | 0 |
| Generated / shown / rejected statements | 26 / 22 / 4 | 36 / 36 / 0 | 62 / 58 / 4 |

Coverage: AI Act, DORA, NIST AI RMF, NIST GenAI Profile, and the Transparency,
Copyright and Safety/Security chapters of the GPAI Code. This is a small development
set, not held-out validation. A source-locator hit is not a complete-answer score.

## Statement-by-statement source assessment

All 62 statements were compared with their own recorded quotations by the assistant,
not an independent domain expert. High-level NIST function descriptions are assessed
as descriptions of intended roles/capabilities, not guarantees of organisational outcomes.

| Shown statements | Supported | Partial | Wrong |
| --- | --- | --- | --- |
| EU (22) | 18 | 4 | 0 |
| Guidance (36) | 28 | 7 | 1 |
| Combined (58) | 46 | 11 | 1 |

All 58 shown statements were labelled supported by the model. The source assessment
disagrees on twelve. Of the four rejected EU statements, three rejections are justified
and one is false; guidance has no rejected statements in this run.

Observed limitations include missing exemptions and safeguards, compressed alternative
conditions, and a persistent actor error in GPAI02: a duty on recipients is assigned
to signatories to ensure recipient behaviour. GPAI01 omits the qualifying open-source
exception, GPAI03 omits conditions for protocol versions/alternatives, and GPAI04
replaces specified assessment triggers with a vague timing condition. EU omissions
and answer-coverage gaps are recorded in the [EU review](azure-eu-review-2026-11-25.md).

The earlier guidance 8/10 citation score and this 10/10 score are not a clean model
comparison: expected pages were also corrected for two Transparency cases. No
retrieval algorithm or threshold was changed. Original reports were not rescored.

Total recorded usage: 112,611 tokens. Across all 22 cases, latency median is 4.526 s
and maximum 19.263 s. Deployment names are recorded by the reports; resolved model
versions and tested application commit IDs are not.

## Latest narrow correction

After these two runs, the reference-qualifier rule was corrected so that a condition
on one article reference is not automatically imposed on a claim about another.
The correction passed 158 offline tests and lint. It does not repair all semantic
model errors listed above and these original run results have not been relabelled.

The [single targeted case](../eval/reference-scope.json) requests verification tasks
under Article 54(3)(a) and expects that exact source unit. It checks the later narrow
change without changing either full development set. Its live result remains pending:

```bash
REGRAG_BACKEND=azure python -m regrag eval --cases eval/reference-scope.json --output .local/azure-reference-scope
```

No new import, embedding or infrastructure is needed. These CLI results do not by
themselves attest a new Container Apps image revision. Preserve the working environment
until the targeted result and any final deployed-image check are captured, then record
cleanup. Answer-quality limitations remain explicit even after technical checks finish.
