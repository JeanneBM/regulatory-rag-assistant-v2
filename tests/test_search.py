from types import SimpleNamespace

import pytest
from azure.core.exceptions import ResourceNotFoundError

from conftest import FakeOpenAI, unit
from regrag.embeddings import AzureEmbedder, embedding_text
from regrag.retrieval import AzureSearchRetriever, LocalRetriever
from regrag.search_index import SEMANTIC_CONFIG, VECTOR_FIELD, SearchPublisher, index_definition, index_name


class FakeSearchClient:
    def __init__(self, service, name):
        self.service, self.name = service, name

    def upload_documents(self, documents):
        if self.service.reject:
            return [SimpleNamespace(key=d["id"], succeeded=False) for d in documents]
        self.service.documents.setdefault(self.name, []).extend(documents)
        return [SimpleNamespace(key=d["id"], succeeded=True) for d in documents]

    def get_document_count(self):
        return len(self.service.documents.get(self.name, []))


class FakeIndexService:
    def __init__(self):
        self.indexes, self.documents, self.aliases = {}, {}, {}
        self.reject = False

    def list_index_names(self):
        return list(self.indexes)

    def create_index(self, index):
        self.indexes[index.name] = index

    def delete_index(self, name):
        assert name not in self.aliases.values(), "aliased index must not be deleted"
        self.indexes.pop(name)
        self.documents.pop(name, None)

    def get_search_client(self, name):
        return FakeSearchClient(self, name)

    def get_alias(self, name):
        if name not in self.aliases:
            raise ResourceNotFoundError("no alias")
        return SimpleNamespace(indexes=[self.aliases[name]])

    def create_or_update_alias(self, alias):
        self.aliases[alias.name] = alias.indexes[0]


def publisher(service, client):
    return SearchPublisher(service, AzureEmbedder(client, "emb", 4), alias="regrag", prefix="regrag",
                           dimensions=4, sleep=lambda _: None, log=lambda _: None)


UNITS = [unit(), unit("AI_ACT-art-4", "AI_ACT", "4", "Providers and deployers of AI systems shall take "
                      "measures to ensure a sufficient level of AI literacy of their staff.", "Article 4",
                      "AI literacy")]


def test_index_definition_is_hybrid_and_semantic():
    definition = index_definition("regrag-abc", 1536).as_dict()
    fields = {f["name"]: f for f in definition["fields"]}
    assert fields["id"]["key"] is True
    assert fields["act"]["filterable"] is True
    assert fields["text"]["analyzer"] == "en.microsoft"
    assert fields[VECTOR_FIELD]["dimensions"] == 1536
    assert definition["semantic"]["defaultConfiguration"] == SEMANTIC_CONFIG
    assert "semantic" not in index_definition("regrag-abc", 1536, semantic=False).as_dict()


def test_index_name_changes_with_corpus_or_embedding():
    assert index_name("regrag", "a" * 64, "emb:4") != index_name("regrag", "b" * 64, "emb:4")
    assert index_name("regrag", "a" * 64, "emb:4") != index_name("regrag", "a" * 64, "emb:8")


def test_publish_builds_swaps_alias_and_prunes_old_indexes():
    service, client = FakeIndexService(), FakeOpenAI()
    service.indexes = {"regrag-old1": None, "regrag-old2": None, "other-index": None}
    service.aliases["regrag"] = "regrag-old2"
    result = publisher(service, client).publish(UNITS, "d" * 64)
    assert result["built"] and result["previous"] == "regrag-old2"
    assert service.aliases["regrag"] == result["index"]
    assert set(service.indexes) == {result["index"], "regrag-old2", "other-index"}
    assert result["pruned"] == ["regrag-old1"]
    stored = service.documents[result["index"]]
    assert [d["id"] for d in stored] == [u["id"] for u in UNITS]
    assert stored[0][VECTOR_FIELD] == [float(len(embedding_text(UNITS[0])) % 7), 1.0, 0.0, 0.5]


def test_unchanged_corpus_reuses_index_without_embedding():
    service, client = FakeIndexService(), FakeOpenAI()
    first = publisher(service, client).publish(UNITS, "d" * 64)
    client.embedding_requests.clear()
    second = publisher(service, client).publish(UNITS, "d" * 64)
    assert second["index"] == first["index"] and not second["built"]
    assert client.embedding_requests == []


def test_rejected_upload_never_moves_alias():
    service, client = FakeIndexService(), FakeOpenAI()
    service.aliases["regrag"] = "regrag-live"
    service.indexes["regrag-live"] = None
    service.reject = True
    with pytest.raises(RuntimeError, match="rejected"):
        publisher(service, client).publish(UNITS, "d" * 64)
    assert service.aliases["regrag"] == "regrag-live"


def test_local_retriever_ranks_filters_and_abstains():
    retriever = LocalRetriever(UNITS)
    assert retriever.retrieve("ICT risk management framework")[0]["id"] == UNITS[0]["id"]
    assert retriever.retrieve("ICT risk management framework", "AI_ACT") == []
    assert retriever.retrieve("chocolate cake recipe") == []
    with pytest.raises(ValueError, match="Unknown act"):
        retriever.retrieve("anything", "DORA' or act ne '")


class RecordingSearch:
    def __init__(self, results):
        self.results, self.calls = results, []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.results)


def test_azure_retriever_runs_hybrid_semantic_query_and_applies_threshold():
    results = [{**UNITS[0], "@search.score": 0.03, "@search.reranker_score": 2.7},
               {**UNITS[1], "@search.score": 0.02, "@search.reranker_score": 0.4}]
    search = RecordingSearch(results)
    hits = AzureSearchRetriever(search, AzureEmbedder(FakeOpenAI(), "emb", 4)).retrieve(
        "ICT framework?", "DORA")
    assert [h["id"] for h in hits] == [UNITS[0]["id"]]
    assert hits[0]["reranker_score"] == 2.7
    call = search.calls[0]
    assert call["search_text"] == "ICT framework?"
    assert call["filter"] == "act eq 'DORA'"
    assert call["query_type"] == "semantic" and call["semantic_configuration_name"] == SEMANTIC_CONFIG
    assert call["vector_queries"][0].as_dict()["fields"] == VECTOR_FIELD


def test_azure_retriever_without_semantic_ranker_keeps_fused_results():
    search = RecordingSearch([{**UNITS[0], "@search.score": 0.03, "@search.reranker_score": None}])
    hits = AzureSearchRetriever(search, AzureEmbedder(FakeOpenAI(), "emb", 4), semantic=False).retrieve("x?")
    assert len(hits) == 1 and "query_type" not in search.calls[0]
