#!/bin/sh
# azd postdeploy hook: run the ingest job with the image azd just deployed, then
# start the first import so the search alias exists before the first question.
set -eu

: "${AZURE_RESOURCE_GROUP:?run through azd}"
: "${INGEST_JOB_NAME:?run through azd}"
: "${SERVICE_WEB_IMAGE_NAME:?run through azd deploy}"

az config set extension.use_dynamic_install=yes_without_prompt --only-show-errors >/dev/null

echo "Ingest job $INGEST_JOB_NAME -> $SERVICE_WEB_IMAGE_NAME"
az containerapp job update --name "$INGEST_JOB_NAME" --resource-group "$AZURE_RESOURCE_GROUP" \
  --image "$SERVICE_WEB_IMAGE_NAME" --output none

if [ "${REGRAG_SKIP_INGEST:-false}" != "true" ]; then
  az containerapp job start --name "$INGEST_JOB_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --output none
  echo "Import started. Follow it with:"
  echo "  az containerapp job execution list -n $INGEST_JOB_NAME -g $AZURE_RESOURCE_GROUP -o table"
fi
