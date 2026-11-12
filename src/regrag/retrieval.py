"""Retrieval backends.

* AzureSearchRetriever: hybrid BM25 + vector query (reciprocal rank fusion) in Azure
  AI Search, re-ranked by the semantic ranker. Abstains when no result reaches the
  reranker threshold.
* LocalRetriever: TF-IDF over the local corpus for offline development and CI.

Both return evidence dictionaries with the unit fields plus scores. Scores are
ranking signals, not confidence; thresholds are provisional until calibrated.
"""
from regrag.sources import ACTS


def _check_act(act: str | None) -> None:
    # The act key is interpolated into an OData filter, so only known keys pass.
    if act is not None and act not in ACTS:
        raise ValueError(f"Unknown act filter: {act}")


class LocalRetriever:
    name = "local-tfidf"

    def __init__(self, units: list[dict], min_score: float = 0.05, top_k: int = 8):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.units = units
        self.min_score = min_score
        self.top_k = top_k
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(
            [f"{u.get('article_title', '')}\n{u['text']}" for u in units]) if units else None

    def retrieve(self, question: str, act: str | None = None) -> list[dict]:
        _check_act(act)
        if not question.strip() or self.matrix is None:
            return []
        from sklearn.metrics.pairwise import cosine_similarity
        scores = cosine_similarity(self.vectorizer.transform([question]), self.matrix)[0]
        ranked = sorted(((score, i) for i, score in enumerate(scores)
                         if act is None or self.units[i]["act"] == act), reverse=True)
        return [dict(self.units[i], score=float(score), reranker_score=None)
                for score, i in ranked[:self.top_k] if score >= self.min_score]


class AzureSearchRetriever:
    name = "azure-ai-search-hybrid"

    def __init__(self, search_client, embedder, top_k: int = 8, semantic: bool = True,
                 min_reranker_score: float = 1.2, candidates: int = 50):
        self.client = search_client
        self.embedder = embedder
        self.top_k = top_k
        self.semantic = semantic
        self.min_reranker_score = min_reranker_score
        self.candidates = candidates

    def retrieve(self, question: str, act: str | None = None) -> list[dict]:
        from azure.search.documents.models import VectorizedQuery

        from regrag.search_index import RETRIEVABLE, SEMANTIC_CONFIG, VECTOR_FIELD
        _check_act(act)
        if not question.strip():
            return []
        vector = self.embedder.embed([question])[0]
        options = dict(
            search_text=question,
            vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=self.candidates,
                                            fields=VECTOR_FIELD)],
            filter=f"act eq '{act}'" if act else None,
            select=RETRIEVABLE,
            top=self.top_k,
        )
        if self.semantic:
            options.update(query_type="semantic", semantic_configuration_name=SEMANTIC_CONFIG,
                           semantic_error_mode="fail")
        hits = []
        for result in self.client.search(**options):
            reranker = result.get("@search.reranker_score")
            if self.semantic and (reranker is None or reranker < self.min_reranker_score):
                continue
            hits.append({**{key: result.get(key) for key in RETRIEVABLE},
                         "score": result.get("@search.score"), "reranker_score": reranker})
        return hits
