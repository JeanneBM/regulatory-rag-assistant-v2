"""Azure AI Search index: schema, versioned build and atomic alias swap.

Every corpus snapshot gets its own index, named after the corpus digest, the
embedding deployment and the schema version. The application queries an alias.
A new index becomes visible only after all documents are uploaded and counted, so
a failed import never leaves the application with a partial index. Re-running the
import on an unchanged corpus re-uses the existing index and embeds nothing.
"""
import hashlib
import time

from regrag.embeddings import embedding_text

SCHEMA_VERSION = "1"
VECTOR_FIELD = "content_vector"
SEMANTIC_CONFIG = "regrag-semantic"
VECTOR_PROFILE = "regrag-hnsw-profile"
RETRIEVABLE = ["id", "act", "celex", "article", "article_title", "paragraph", "point",
               "label", "text", "url", "ordinal"]


def index_name(prefix: str, corpus_digest: str, embedding_identity: str) -> str:
    key = f"{SCHEMA_VERSION}|{corpus_digest}|{embedding_identity}"
    return f"{prefix}-{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def index_definition(name: str, dimensions: int, semantic: bool = True):
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        HnswParameters,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )
    string = SearchFieldDataType.String
    fields = [
        SimpleField(name="id", type=string, key=True),
        SimpleField(name="act", type=string, filterable=True, facetable=True),
        SimpleField(name="celex", type=string, filterable=True),
        SimpleField(name="article", type=string, filterable=True),
        SimpleField(name="paragraph", type=string, filterable=True),
        SimpleField(name="point", type=string),
        SearchableField(name="label", analyzer_name="en.microsoft"),
        SearchableField(name="article_title", analyzer_name="en.microsoft"),
        SearchableField(name="text", analyzer_name="en.microsoft"),
        SimpleField(name="url", type=string),
        SimpleField(name="ordinal", type=SearchFieldDataType.Int32, sortable=True),
        SearchField(name=VECTOR_FIELD, type="Collection(Edm.Single)", searchable=True,
                    vector_search_dimensions=dimensions, vector_search_profile_name=VECTOR_PROFILE,
                    stored=False),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="regrag-hnsw",
                                               parameters=HnswParameters(metric="cosine"))],
        profiles=[VectorSearchProfile(name=VECTOR_PROFILE, algorithm_configuration_name="regrag-hnsw")],
    )
    semantic_search = SemanticSearch(
        default_configuration_name=SEMANTIC_CONFIG,
        configurations=[SemanticConfiguration(
            name=SEMANTIC_CONFIG,
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="article_title"),
                content_fields=[SemanticField(field_name="text")],
                keywords_fields=[SemanticField(field_name="label")],
            ),
        )],
    ) if semantic else None
    return SearchIndex(name=name, fields=fields, vector_search=vector_search,
                       semantic_search=semantic_search)


def to_document(unit: dict, vector: list[float]) -> dict:
    document = {field: unit.get(field) for field in RETRIEVABLE}
    document[VECTOR_FIELD] = vector
    return document


class SearchPublisher:
    def __init__(self, index_client, embedder, alias: str, prefix: str, dimensions: int,
                 semantic: bool = True, batch_size: int = 200, poll_seconds: float = 5,
                 poll_timeout: float = 300, sleep=time.sleep, log=print):
        self.index_client = index_client
        self.embedder = embedder
        self.alias = alias
        self.prefix = prefix
        self.dimensions = dimensions
        self.semantic = semantic
        self.batch_size = batch_size
        self.poll_seconds = poll_seconds
        self.poll_timeout = poll_timeout
        self.sleep = sleep
        self.log = log

    def _current_alias_target(self) -> str | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            alias = self.index_client.get_alias(self.alias)
        except ResourceNotFoundError:
            return None
        return alias.indexes[0] if alias.indexes else None

    def _count(self, name: str) -> int:
        return self.index_client.get_search_client(name).get_document_count()

    def _build(self, name: str, units: list[dict]) -> None:
        self.index_client.create_index(index_definition(name, self.dimensions, self.semantic))
        vectors = self.embedder.embed([embedding_text(unit) for unit in units])
        client = self.index_client.get_search_client(name)
        documents = [to_document(unit, vector) for unit, vector in zip(units, vectors, strict=True)]
        for start in range(0, len(documents), self.batch_size):
            results = client.upload_documents(documents[start:start + self.batch_size])
            failed = [r.key for r in results if not r.succeeded]
            if failed:
                raise RuntimeError(f"Search rejected {len(failed)} documents, e.g. {failed[:3]}")
        deadline = time.monotonic() + self.poll_timeout
        while (count := self._count(name)) != len(units):
            if time.monotonic() > deadline:
                raise RuntimeError(f"Index {name} reports {count} of {len(units)} documents")
            self.sleep(self.poll_seconds)

    def publish(self, units: list[dict], corpus_digest: str) -> dict:
        from azure.search.documents.indexes.models import SearchAlias
        name = index_name(self.prefix, corpus_digest, self.embedder.identity)
        existing = set(self.index_client.list_index_names())
        built = False
        if name in existing and self._count(name) == len(units):
            self.log(f"Index {name} already holds this corpus; nothing to embed")
        else:
            if name in existing:
                self.log(f"Index {name} is incomplete; rebuilding")
                self.index_client.delete_index(name)
            self.log(f"Building index {name} with {len(units)} documents")
            self._build(name, units)
            built = True
        previous = self._current_alias_target()
        self.index_client.create_or_update_alias(SearchAlias(name=self.alias, indexes=[name]))
        self.log(f"Alias {self.alias} -> {name}")
        keep = {name, previous}
        pruned = []
        for other in self.index_client.list_index_names():
            if other.startswith(f"{self.prefix}-") and other not in keep:
                self.index_client.delete_index(other)
                pruned.append(other)
        return {"index": name, "built": built, "previous": previous, "pruned": pruned,
                "embedding": self.embedder.identity, "embedding_tokens": self.embedder.tokens}
