"""Azure SDK clients authenticated with Microsoft Entra ID.

In Azure Container Apps, `DefaultAzureCredential` uses the user-assigned managed
identity named by AZURE_CLIENT_ID. Locally it falls back to the Azure CLI login.
No connection strings or account keys are used.
"""
from functools import lru_cache

from regrag.config import Settings

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


@lru_cache(maxsize=1)
def credential():
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def openai_client(settings: Settings):
    from openai import AzureOpenAI
    options = dict(azure_endpoint=settings.openai_endpoint,
                   api_version=settings.openai_api_version, timeout=60, max_retries=2)
    if settings.openai_api_key:
        return AzureOpenAI(api_key=settings.openai_api_key, **options)
    from azure.identity import get_bearer_token_provider
    return AzureOpenAI(azure_ad_token_provider=get_bearer_token_provider(credential(), COGNITIVE_SCOPE),
                       **options)


def search_client(settings: Settings, index_name: str | None = None):
    from azure.search.documents import SearchClient
    return SearchClient(settings.search_endpoint, index_name or settings.search_alias, credential())


def search_index_client(settings: Settings):
    from azure.search.documents.indexes import SearchIndexClient
    return SearchIndexClient(settings.search_endpoint, credential())


def blob_container(settings: Settings):
    from azure.storage.blob import BlobServiceClient
    service = BlobServiceClient(settings.storage_account_url, credential=credential())
    return service.get_container_client(settings.storage_container)
