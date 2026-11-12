// Separate identities: the web app can only read; the ingest job can write.
param location string
param tags object
param webName string
param ingestName string

resource web 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: webName
  location: location
  tags: tags
}

resource ingest 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: ingestName
  location: location
  tags: tags
}

output webId string = web.id
output webClientId string = web.properties.clientId
output webPrincipalId string = web.properties.principalId
output ingestId string = ingest.id
output ingestClientId string = ingest.properties.clientId
output ingestPrincipalId string = ingest.properties.principalId
