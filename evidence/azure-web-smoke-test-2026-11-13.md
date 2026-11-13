# Azure Container Apps deployment smoke test

Date: 13 November 2026. Region: Poland Central.

The operator reported a successful `azd up` and a successful Container Apps ingestion job. The checks below were sent directly to the deployed HTTP endpoint after ingestion.

| Check | Observed result |
| --- | --- |
| `/healthz` | HTTP 200, version 2.0.0 |
| `/readyz` | HTTP 200, ready |
| `/api/info` | azure-ai-search-hybrid, generation enabled: true, verification: model, policy: strict |
| DORA ICT risk management framework | answered. Citations: DORA Article 6(8), point (b), DORA Article 6(3) |
| VAT rate control | insufficient_evidence. 0 claims shown |

Smoke test: **passed**. The checks cover the deployed API, Azure AI Search retrieval and the Azure OpenAI response path. The browser interaction was tested separately on localhost. Two requests do not establish retrieval quality across the ten-question pilot. Corpus hash and synchronization metadata were not populated in the API response at the time of the check.

[Captured API responses](azure-web-smoke-test-2026-11-13.json)
