# Azure web smoke — 25 November 2026

Environment: `regrag-final-20261125`, resource group `rg-regrag-final-20261125`.
Evidence: operator-supplied screenshots of the deployed web application in this session.
The UI identifies the backend as `azure-ai-search-hybrid` and verification as `model`.

| Final trial | Source filter | Observed outcome |
| --- | --- | --- |
| What action does MS-2.5-003 recommend about checking sources and citations? | NIST GenAI Profile | Answer recommends reviewing and verifying sources and citations during pre-deployment risk measurement and ongoing monitoring. Citation: PDF viewer page 35, part 1; verifier label SUPPORTED. |
| How do signatories respect rights reservations expressed through robots.txt? | GPAI Code: Copyright | Answer describes signatories' crawler commitments, robots.txt and RFC 9309, with technical-feasibility qualifications. Citation: PDF viewer page 5, part 1; verifier label SUPPORTED. |
| How do I bake a chocolate cake? | NIST AI RMF 1.0 | No evidence passed the retrieval threshold; application withheld an answer. This exercises the retrieval gate, not a model-based refusal. |

Final smoke outcome: two cited answers and one out-of-scope abstention observed.
Earlier NIST attempts returned ResourceNotFoundError while an import execution was
reported Running. The streaming-log command later found no replicas. Successful
later requests show recovery; the exact cause of the earlier error was not established.

## Evidence limits

- This is a three-question manual smoke, not a full evaluation of all seven sources.
- SUPPORTED is the application's verifier label, not independent certification.
- The screenshots do not provide raw responses, token usage, timings, deployed image digest
  or a complete ingest execution record. None are inferred.
- The local guidance development set remains 9/10 for expected retrieval locators.
- Resource deletion and billing cleanup are **pending operator confirmation**.

## Cleanup

From the same local azd environment:

```bash
azd down --purge
```

After deletion completes, verify the recorded group is absent:

```bash
az group exists --name rg-regrag-final-20261125
```

Expected result: `false`. Record the actual output before marking cleanup complete.
