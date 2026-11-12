# azd postdeploy hook (Windows): see postdeploy.sh.
$ErrorActionPreference = 'Stop'
foreach ($name in 'AZURE_RESOURCE_GROUP', 'INGEST_JOB_NAME', 'SERVICE_WEB_IMAGE_NAME') {
    if (-not [Environment]::GetEnvironmentVariable($name)) { throw "$name is not set; run through azd deploy" }
}
az config set extension.use_dynamic_install=yes_without_prompt --only-show-errors | Out-Null

Write-Host "Ingest job $env:INGEST_JOB_NAME -> $env:SERVICE_WEB_IMAGE_NAME"
az containerapp job update --name $env:INGEST_JOB_NAME --resource-group $env:AZURE_RESOURCE_GROUP `
    --image $env:SERVICE_WEB_IMAGE_NAME --output none
if ($LASTEXITCODE -ne 0) { throw 'job update failed' }

if ($env:REGRAG_SKIP_INGEST -ne 'true') {
    az containerapp job start --name $env:INGEST_JOB_NAME --resource-group $env:AZURE_RESOURCE_GROUP --output none
    if ($LASTEXITCODE -ne 0) { throw 'job start failed' }
    Write-Host "Import started. Follow it with:"
    Write-Host "  az containerapp job execution list -n $env:INGEST_JOB_NAME -g $env:AZURE_RESOURCE_GROUP -o table"
}
