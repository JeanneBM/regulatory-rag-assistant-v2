# Regulatory RAG v2 deployment and test manual

This guide reproduces the web validation performed on 13 November 2026. The browser test used local TF-IDF retrieval with Azure OpenAI. The Azure smoke test sent HTTP requests directly to the deployed FastAPI API using hybrid Azure AI Search and Azure OpenAI.

## 1. Local browser test

From the repository root, with Python 3.11+, Azure CLI and an existing Azure OpenAI chat deployment:

```bash
python -m pip install -e ".[local]"
az login
export REGRAG_BACKEND=local
export AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
export AZURE_OPENAI_CHAT_DEPLOYMENT="<your-chat-deployment>"
python -m regrag serve
```

Open http://127.0.0.1:8000. Enter each question from the table below, submit it, and compare the displayed result. The recorded browser run used the default **Both acts** filter and GPT-4.1 nano. For the answer, open the citation and check that it points to the relevant EUR-Lex provision.

| Case | Question | Pass criterion |
| --- | --- | --- |
| Answer with citations | What does DORA say about the ICT risk management framework? | An answer appears with a quotation from DORA Article 6 and a corresponding EUR-Lex link. |
| Abstention control | What VAT rate does DORA set for the ICT risk management framework of financial entities? | The UI displays “Not enough evidence to answer” and makes no VAT claim. |

Recorded browser evidence: [answer with citations](web-pilot-dora-cited-answer.pdf) and [abstention](web-pilot-dora-out-of-scope-abstention.pdf).

## 2. Deploy a temporary Azure environment

Use Git Bash or another Bash shell with Azure CLI and Azure Developer CLI installed. The deploying identity needs permission to create resources and assign the Bicep-defined roles. Confirm the active subscription before provisioning.

```bash
azd version
az login
azd auth login
az account show --query '{Name:name,State:state}' -o table

azd env new regrag-web-test
azd env set AZURE_SUBSCRIPTION_ID "$(az account show --query id -o tsv)"
azd env set AZURE_LOCATION polandcentral
azd up
```

Use `azd env select regrag-web-test` if the environment already exists. The default ingress is public. To restrict it, set `REGRAG_ALLOWED_IP_RANGES` to your public IP CIDR before running `azd up`.

Check the import after the post-deploy hook:

```bash
az containerapp job execution list \
  --name "$(azd env get-value INGEST_JOB_NAME)" \
  --resource-group "$(azd env get-value AZURE_RESOURCE_GROUP)" \
  --query '[].{Execution:name,Status:properties.status,Started:properties.startTime}' \
  -o table
```

Wait for the current import to report `Succeeded`. In the recorded deployment, `/readyz` already returned HTTP 200 while answer requests still failed with `ResourceNotFoundError`. Both questions succeeded after the import completed.

## 3. Test the deployed API

```bash
WEB_URL="$(azd env get-value WEB_URL)"
WEB_URL="${WEB_URL%/}"
for route in healthz readyz api/info; do
  curl --fail-with-body -sS "$WEB_URL/$route"
  printf '\n'
done

curl --fail-with-body -sS "$WEB_URL/api/ask" \
  -H 'Content-Type: application/json' \
  --data '{"act":"DORA","question":"What does DORA say about the ICT risk management framework?"}'

curl --fail-with-body -sS "$WEB_URL/api/ask" \
  -H 'Content-Type: application/json' \
  --data '{"act":"DORA","question":"What VAT rate does DORA set for the ICT risk management framework of financial entities?"}'
```

| Check | Pass criterion |
| --- | --- |
| `/healthz` and `/readyz` | HTTP 200 with `ok` and `ready`, respectively. |
| `/api/info` | Backend is `azure-ai-search-hybrid`, generation is enabled and verification is `model`. |
| DORA answer | `status: answered` with at least one claim citing DORA Article 6. |
| VAT control | `status: insufficient_evidence` and zero claims. |

Both Azure API cases passed. The corpus metadata fields were empty in the captured responses. See the [Azure smoke-test report](azure-web-smoke-test-2026-11-13.md) and [captured API responses](azure-web-smoke-test-2026-11-13.json). The separate [ten-question CLI evaluation](eval-20261113T130444Z-review.md) used local retrieval. The Azure smoke test covered two questions.

## 4. Clean up

Save your test output, then remove the temporary Azure environment. Azure AI Search Basic accrues charges while provisioned.

```bash
azd down --environment regrag-web-test
az group exists --name rg-regrag-web-test
```

Check the environment shown in the deletion prompt before confirming. The final command should return `false` after deletion in the deployment subscription.
