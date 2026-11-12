// Container Apps environment, the web app (FastAPI + UI) and the scheduled ingest job.
param location string
param tags object
param environmentName string
param webName string
param jobName string
param logAnalyticsName string
@secure()
param appInsightsConnectionString string
param registryLoginServer string
param webIdentityId string
param webClientId string
param ingestIdentityId string
param ingestClientId string
param webImage string
param jobImage string
param allowedIpRanges array
param ingestSchedule string
@description('Non-secret settings shared by the web app and the job.')
param settings object

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsName
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}

var sharedEnv = [for item in items(settings): { name: item.key, value: item.value }]
var telemetryEnv = [{ name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }]
var secrets = [{ name: 'appinsights-connection-string', value: appInsightsConnectionString }]

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: webName
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${webIdentityId}': {} } }
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        ipSecurityRestrictions: [
          for (range, i) in allowedIpRanges: { name: 'allow-${i}', action: 'Allow', ipAddressRange: range }
        ]
      }
      registries: [{ server: registryLoginServer, identity: webIdentityId }]
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat(sharedEnv, telemetryEnv, [{ name: 'AZURE_CLIENT_ID', value: webClientId }])
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/readyz', port: 8000 }, periodSeconds: 15 }
          ]
        }
      ]
      // Scale to zero when idle: no compute cost without traffic.
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '20' } } }]
      }
    }
  }
}

resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${ingestIdentityId}': {} } }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      scheduleTriggerConfig: { cronExpression: ingestSchedule, parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: registryLoginServer, identity: ingestIdentityId }]
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'ingest'
          image: jobImage
          command: ['python', '-m', 'regrag']
          args: ['ingest', '--target', 'azure']
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: concat(sharedEnv, telemetryEnv, [{ name: 'AZURE_CLIENT_ID', value: ingestClientId }])
        }
      ]
    }
  }
}

output webUrl string = 'https://${web.properties.configuration.ingress.fqdn}'
output jobName string = job.name
