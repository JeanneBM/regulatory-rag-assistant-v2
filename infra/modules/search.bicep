param location string
param tags object
param name string

@allowed(['free', 'basic', 'standard'])
param sku string

@allowed(['disabled', 'free', 'standard'])
param semanticRanker string

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: sku }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    // RBAC only: no admin or query keys.
    disableLocalAuth: true
    publicNetworkAccess: 'enabled'
    semanticSearch: sku == 'free' ? null : semanticRanker
  }
}

output name string = search.name
output endpoint string = 'https://${search.name}.search.windows.net'
