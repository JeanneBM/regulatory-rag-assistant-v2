# Final deployed-web smoke — 25 November 2026

**Both UI smoke checks passed in user-provided screenshots after the user reported
deployment completion.** Both requests used the visible `All sources` selector.
Original screenshots remain private; no deployment URL, image digest or raw operator
logs are published here.

| Check | Observed result |
| --- | --- |
| SCOPE01 question about Article 54(3)(a) | Two visible assertions: verifying Annex XI documentation and fulfilment of Article 53 obligations, each citing Article 54(3), point (a). The displayed source supports both. |
| Unrelated chocolate-cake question | `Not enough evidence to answer`, with `No evidence passed the retrieval threshold`. |
| Previous-answer display | No prior answer cards or citations appear in the abstention screenshot. |
| Backend/corpus indicator | The abstention footer reports Azure hybrid search and model verification, with the same corpus-prefix indicator as the CLI runs. |

The positive screenshot shows the complete first source quotation; the lower part of
the second answer card is outside the captured frame. These are visual observations,
not raw API reports, a browser automation trace, or proof of a particular image digest.
The screenshots close the planned functional UI smoke; they do not reclassify the
11 partial and one wrong statement in the earlier full evaluation.

The [22-case full evaluation](azure-full-evaluation-2026-11-25.md) and
[SCOPE01 live regression](reference-scope-azure-2026-11-25.md) retain their original results.

**Cleanup confirmation is the remaining lab operation.** After recording both UI
results, remove the dedicated environment and confirm the recorded resource group
is absent. No further model evaluation is required for this session's validation
record. Final cleanup output has not yet been supplied.
