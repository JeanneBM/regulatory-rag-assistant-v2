// Least-privilege data-plane roles.
//   web    : OpenAI User, Search Index Data Reader, Blob Data Reader (container), AcrPull, Metrics Publisher
//   ingest : OpenAI User, Search Service + Index Data Contributor, Blob Data Contributor (container),
//            AcrPull, Metrics Publisher
//   user   : the ingest roles, for running the CLI against Azure from a workstation
param openAiName string
param searchName string
param storageName string
param containerName string
param registryName string
param appInsightsName string
param webPrincipalId string
param ingestPrincipalId string
param userPrincipalId string = ''
@allowed(['User', 'ServicePrincipal'])
param userPrincipalType string = 'User'

var roles = {
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  blobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
  blobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  metricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb'
}
var web = { id: webPrincipalId, type: 'ServicePrincipal' }
var ingest = { id: ingestPrincipalId, type: 'ServicePrincipal' }
var users = empty(userPrincipalId) ? [] : [{ id: userPrincipalId, type: userPrincipalType }]

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = { name: openAiName }
resource search 'Microsoft.Search/searchServices@2023-11-01' existing = { name: searchName }
resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  name: '${storageName}/default/${containerName}'
}
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: registryName }
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = { name: appInsightsName }

var writers = concat([ingest], users)
var openAiGrants = map(concat([web, ingest], users), p => { principal: p, role: roles.openAiUser })
var searchGrants = concat(
  [{ principal: web, role: roles.searchIndexDataReader }],
  map(writers, p => { principal: p, role: roles.searchIndexDataContributor }),
  map(writers, p => { principal: p, role: roles.searchServiceContributor })
)
var blobGrants = concat(
  [{ principal: web, role: roles.blobDataReader }],
  map(writers, p => { principal: p, role: roles.blobDataContributor })
)
var acrGrants = map([web, ingest], p => { principal: p, role: roles.acrPull })
var monitorGrants = map(concat([web, ingest], users), p => { principal: p, role: roles.metricsPublisher })

resource openAiAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for grant in openAiGrants: {
    scope: openAi
    name: guid(openAi.id, grant.principal.id, grant.role)
    properties: {
      principalId: grant.principal.id
      principalType: grant.principal.type
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', grant.role)
    }
  }
]

resource searchAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for grant in searchGrants: {
    scope: search
    name: guid(search.id, grant.principal.id, grant.role)
    properties: {
      principalId: grant.principal.id
      principalType: grant.principal.type
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', grant.role)
    }
  }
]

resource blobAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for grant in blobGrants: {
    scope: container
    name: guid(container.id, grant.principal.id, grant.role)
    properties: {
      principalId: grant.principal.id
      principalType: grant.principal.type
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', grant.role)
    }
  }
]

resource acrAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for grant in acrGrants: {
    scope: registry
    name: guid(registry.id, grant.principal.id, grant.role)
    properties: {
      principalId: grant.principal.id
      principalType: grant.principal.type
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', grant.role)
    }
  }
]

resource monitorAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for grant in monitorGrants: {
    scope: appInsights
    name: guid(appInsights.id, grant.principal.id, grant.role)
    properties: {
      principalId: grant.principal.id
      principalType: grant.principal.type
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', grant.role)
    }
  }
]
