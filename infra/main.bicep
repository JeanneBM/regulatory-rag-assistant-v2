// Regulatory RAG Assistant on Azure.
// Resource group with Azure OpenAI (AI Services), Azure AI Search, Blob Storage,
// Container Registry, Container Apps (web app + scheduled ingest job), Log Analytics
// and Application Insights. Every service disables key-based auth; workloads use
// two user-assigned managed identities with least-privilege data-plane roles.
targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd environment name; prefixes the resource group and tags every resource.')
param environmentName string

@minLength(1)
@description('Region offering the chosen Azure OpenAI models, Azure AI Search and Container Apps, e.g. polandcentral.')
param location string

@description('Object ID of the deploying user or service principal. Gets the data-plane roles needed to run the CLI locally. Empty to skip.')
param principalId string = ''

@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@description('Chat model used for answers and claim verification.')
param chatModelName string = 'gpt-4.1-mini'
param chatModelVersion string = '2025-04-14'
@description('DataZoneStandard keeps model processing inside the data zone (EU for EU regions); GlobalStandard may process in any region.')
param chatDeploymentSku string = 'DataZoneStandard'
@description('Chat deployment capacity in thousands of tokens per minute.')
param chatCapacity int = 30

param embeddingModelName string = 'text-embedding-3-small'
param embeddingModelVersion string = '1'
param embeddingDeploymentSku string = 'DataZoneStandard'
param embeddingCapacity int = 50
param embeddingDimensions int = 1536

@allowed(['free', 'basic', 'standard'])
@description('Azure AI Search tier. Basic is the smallest tier with the semantic ranker and a fixed monthly charge.')
param searchSku string = 'basic'

@allowed(['disabled', 'free', 'standard'])
@description('Semantic ranker plan. Ignored on the free search tier.')
param semanticRanker string = 'free'

@description('Comma-separated CIDR ranges allowed to reach the web app, e.g. "203.0.113.10/32". Empty leaves ingress public.')
param allowedIpRanges string = ''

@description('Weekly import schedule (UTC cron).')
param ingestSchedule string = '17 5 * * 1'

@description('Set by azd: true once the web app has been deployed, so provisioning keeps its image.')
param webAppExists bool = false

@description('Monthly cost budget for the resource group in the billing currency. 0 creates no budget.')
param budgetAmount int = 0
param budgetContactEmail string = ''

var tags = { 'azd-env-name': environmentName, project: 'regulatory-rag-assistant-v2' }
var token = toLower(uniqueString(subscription().id, environmentName, location))
var semanticEnabled = searchSku != 'free' && semanticRanker != 'disabled'
var names = {
  logs: 'log-${token}'
  appInsights: 'appi-${token}'
  openAi: 'oai-${token}'
  search: 'srch-${token}'
  storage: 'st${token}'
  registry: 'cr${token}'
  environment: 'cae-${token}'
  web: 'ca-web-${token}'
  job: 'caj-ingest-${token}'
  webIdentity: 'id-web-${token}'
  ingestIdentity: 'id-ingest-${token}'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  scope: rg
  name: 'monitoring'
  params: { location: location, tags: tags, logAnalyticsName: names.logs, appInsightsName: names.appInsights }
}

module identities 'modules/identities.bicep' = {
  scope: rg
  name: 'identities'
  params: { location: location, tags: tags, webName: names.webIdentity, ingestName: names.ingestIdentity }
}

module openAi 'modules/openai.bicep' = {
  scope: rg
  name: 'openai'
  params: {
    location: location
    tags: tags
    name: names.openAi
    deployments: [
      {
        name: 'chat'
        model: chatModelName
        version: chatModelVersion
        sku: chatDeploymentSku
        capacity: chatCapacity
      }
      {
        name: 'embedding'
        model: embeddingModelName
        version: embeddingModelVersion
        sku: embeddingDeploymentSku
        capacity: embeddingCapacity
      }
    ]
  }
}

module search 'modules/search.bicep' = {
  scope: rg
  name: 'search'
  params: { location: location, tags: tags, name: names.search, sku: searchSku, semanticRanker: semanticRanker }
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storage'
  params: { location: location, tags: tags, name: names.storage, containerName: 'corpus' }
}

module registry 'modules/registry.bicep' = {
  scope: rg
  name: 'registry'
  params: { location: location, tags: tags, name: names.registry }
}

module rbac 'modules/rbac.bicep' = {
  scope: rg
  name: 'rbac'
  params: {
    openAiName: openAi.outputs.name
    searchName: search.outputs.name
    storageName: storage.outputs.name
    containerName: storage.outputs.containerName
    registryName: registry.outputs.name
    appInsightsName: monitoring.outputs.appInsightsName
    webPrincipalId: identities.outputs.webPrincipalId
    ingestPrincipalId: identities.outputs.ingestPrincipalId
    userPrincipalId: principalId
    userPrincipalType: principalType
  }
}

module existingImages 'modules/existing-images.bicep' = {
  scope: rg
  name: 'existing-images'
  params: { exists: webAppExists, webName: names.web, jobName: names.job }
}

module apps 'modules/apps.bicep' = {
  scope: rg
  name: 'apps'
  dependsOn: [rbac]
  params: {
    location: location
    tags: tags
    environmentName: names.environment
    webName: names.web
    jobName: names.job
    logAnalyticsName: monitoring.outputs.logAnalyticsName
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    registryLoginServer: registry.outputs.loginServer
    webIdentityId: identities.outputs.webId
    webClientId: identities.outputs.webClientId
    ingestIdentityId: identities.outputs.ingestId
    ingestClientId: identities.outputs.ingestClientId
    webImage: existingImages.outputs.webImage
    jobImage: existingImages.outputs.jobImage
    allowedIpRanges: filter(map(split(allowedIpRanges, ','), cidr => trim(cidr)), cidr => !empty(cidr))
    ingestSchedule: ingestSchedule
    settings: {
      REGRAG_BACKEND: 'azure'
      AZURE_OPENAI_ENDPOINT: openAi.outputs.endpoint
      AZURE_OPENAI_API_VERSION: '2024-10-21'
      AZURE_OPENAI_CHAT_DEPLOYMENT: 'chat'
      AZURE_OPENAI_EMBEDDING_DEPLOYMENT: 'embedding'
      AZURE_OPENAI_EMBEDDING_DIMENSIONS: string(embeddingDimensions)
      AZURE_SEARCH_ENDPOINT: search.outputs.endpoint
      AZURE_SEARCH_ALIAS: 'regrag'
      AZURE_SEARCH_SEMANTIC_RANKER: string(semanticEnabled)
      AZURE_STORAGE_ACCOUNT_URL: storage.outputs.blobEndpoint
      AZURE_STORAGE_CONTAINER: storage.outputs.containerName
      REGRAG_LOCAL_DIR: '/tmp/regrag'
    }
  }
}

module budget 'modules/budget.bicep' = if (budgetAmount > 0 && !empty(budgetContactEmail)) {
  scope: rg
  name: 'budget'
  params: { amount: budgetAmount, contactEmail: budgetContactEmail }
}

output REGRAG_BACKEND string = 'azure'
output AZURE_SEARCH_ALIAS string = 'regrag'
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer
output AZURE_OPENAI_ENDPOINT string = openAi.outputs.endpoint
output AZURE_OPENAI_CHAT_DEPLOYMENT string = 'chat'
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = 'embedding'
output AZURE_OPENAI_EMBEDDING_DIMENSIONS string = string(embeddingDimensions)
output AZURE_SEARCH_ENDPOINT string = search.outputs.endpoint
output AZURE_SEARCH_SEMANTIC_RANKER string = string(semanticEnabled)
output AZURE_STORAGE_ACCOUNT_URL string = storage.outputs.blobEndpoint
output AZURE_STORAGE_CONTAINER string = storage.outputs.containerName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
output INGEST_JOB_NAME string = apps.outputs.jobName
output WEB_URL string = apps.outputs.webUrl
