// Keeps the deployed images when infrastructure is re-provisioned. On the first
// provision a public placeholder is used until `azd deploy` pushes the real image.
param exists bool
param webName string
param jobName string

var placeholder = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource web 'Microsoft.App/containerApps@2024-03-01' existing = if (exists) {
  name: webName
}

resource job 'Microsoft.App/jobs@2024-03-01' existing = if (exists) {
  name: jobName
}

output webImage string = exists ? web!.properties.template.containers[0].image : placeholder
output jobImage string = exists ? job!.properties.template.containers[0].image : placeholder
