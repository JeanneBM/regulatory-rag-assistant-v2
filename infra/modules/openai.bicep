param location string
param tags object
param name string

@description('Model deployments: name, model, version, sku, capacity.')
param deployments array

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: name
    // Keys are disabled; callers need an Entra ID token and an RBAC role.
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow' }
  }
}

// Deployments on one account must be created one at a time.
@batchSize(1)
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [
  for deployment in deployments: {
    parent: account
    name: deployment.name
    sku: { name: deployment.sku, capacity: deployment.capacity }
    properties: {
      model: { format: 'OpenAI', name: deployment.model, version: deployment.version }
      versionUpgradeOption: 'NoAutoUpgrade'
    }
  }
]

output name string = account.name
output endpoint string = account.properties.endpoint
