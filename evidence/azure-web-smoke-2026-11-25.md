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

## First-run waiting time

**First-run waiting time:** for this fresh seven-source lab, allow roughly **10–15 minutes after the ingest job starts** before trying the first questions. This is an operational allowance based on the 25 November session, not a measured service guarantee; downloads, embedding, indexing and retries can take longer. The web page can already be visible while the search alias is not yet available. `azd deploy` starts import asynchronously and does not wait for it to finish. Prefer a successful ingest execution plus a cited smoke answer as the readiness signal. If it is still failing after that allowance, inspect execution status and logs rather than restarting deployment or launching duplicate imports.

The operator screenshots show failed earlier requests and successful later requests. Exact deployment-to-readiness timing was not captured, so the range above should not be reported as a benchmark.

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
