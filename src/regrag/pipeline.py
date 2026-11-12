"""Question answering pipeline: retrieve -> generate -> verify."""
from time import perf_counter

from regrag import telemetry
from regrag.config import Settings
from regrag.generation import Generator, citation
from regrag.retrieval import AzureSearchRetriever, LocalRetriever
from regrag.sources import ACTS
from regrag.verification import ModelVerifier, verify_claims

DISCLAIMER = ("Research support only. Answers quote the original published acts, not "
              "consolidated versions, and are not legal advice or a compliance assessment.")
EVIDENCE_FIELDS = ["id", "act", "article", "article_title", "paragraph", "point", "label",
                   "text", "url", "score", "reranker_score"]


def _add_usage(total: dict, usage: dict) -> None:
    for key, value in (usage or {}).items():
        total[key] = total.get(key, 0) + value


class Assistant:
    def __init__(self, retriever, generator: Generator | None = None,
                 verifier: ModelVerifier | None = None, policy: str = "strict",
                 manifest: dict | None = None, log_questions: bool = False):
        self.retriever = retriever
        self.generator = generator
        self.verifier = verifier
        self.policy = policy
        self.manifest = manifest
        self.log_questions = log_questions

    def info(self) -> dict:
        manifest = self.manifest or {}
        return {
            "backend": self.retriever.name,
            "generation": self.generator is not None,
            "verification": "model" if self.verifier else "rules",
            "claim_policy": self.policy,
            "acts": {key: {"celex": act.celex, "title": act.title, "url": act.eurlex_url}
                     for key, act in ACTS.items()},
            "corpus": {key: manifest.get(key) for key in ("corpus_sha256", "fetched_at", "units",
                                                          "parser_version")},
            "disclaimer": DISCLAIMER,
        }

    def ask(self, question: str, act: str | None = None) -> dict:
        question = question.strip()
        timings, usage = {}, {}
        with telemetry.span("regrag.ask", backend=self.retriever.name, act=act,
                            question=question if self.log_questions else None,
                            question_chars=len(question)) as root:
            start = perf_counter()
            with telemetry.span("regrag.retrieve") as current:
                evidence = self.retriever.retrieve(question, act)
                current.set_attribute("regrag.evidence_count", len(evidence))
            timings["retrieve_ms"] = round((perf_counter() - start) * 1000)
            result = {
                "question": question, "act_filter": act, "backend": self.retriever.name,
                "evidence": [{**{k: unit.get(k) for k in EVIDENCE_FIELDS}, "citation": citation(unit)}
                             for unit in evidence],
                "claims": [], "rejected_claims": [], "abstention_reason": "",
                "usage": usage, "timings_ms": timings, "disclaimer": DISCLAIMER,
                "corpus_sha256": (self.manifest or {}).get("corpus_sha256"),
            }
            if not evidence:
                result.update(status="insufficient_evidence",
                              abstention_reason="No evidence passed the retrieval threshold.")
            elif self.generator is None:
                result.update(status="retrieval_only")
            else:
                start = perf_counter()
                with telemetry.span("regrag.generate"):
                    generated = self.generator.generate(question, evidence)
                timings["generate_ms"] = round((perf_counter() - start) * 1000)
                _add_usage(usage, generated["usage"])
                if not generated["claims"]:
                    result.update(status="insufficient_evidence", abstention_reason=(
                        generated["abstention_reason"] or "The model found the evidence insufficient."))
                else:
                    start = perf_counter()
                    with telemetry.span("regrag.verify", policy=self.policy):
                        accepted, rejected, verify_usage = verify_claims(
                            generated["claims"], self.verifier, self.policy)
                    timings["verify_ms"] = round((perf_counter() - start) * 1000)
                    _add_usage(usage, verify_usage)
                    result.update(claims=accepted, rejected_claims=rejected)
                    if accepted:
                        result["status"] = "answered"
                    else:
                        result.update(status="insufficient_evidence", abstention_reason=(
                            "No generated claim passed support verification."))
            timings["total_ms"] = sum(timings.values())
            root.set_attribute("regrag.status", result["status"])
            root.set_attribute("regrag.claims_accepted", len(result["claims"]))
            root.set_attribute("regrag.claims_rejected", len(result["rejected_claims"]))
            for key, value in usage.items():
                root.set_attribute(f"regrag.tokens.{key}", value)
        return result


def build_assistant(settings: Settings, log=print) -> Assistant:
    """Wire the configured backend. Azure calls use Entra ID, never keys."""
    from regrag import azure_clients
    client = azure_clients.openai_client(settings) if settings.openai_endpoint else None
    manifest = None
    if settings.backend == "azure":
        from regrag.embeddings import AzureEmbedder
        embedder = AzureEmbedder(client, settings.embedding_deployment, settings.embedding_dimensions)
        retriever = AzureSearchRetriever(
            azure_clients.search_client(settings), embedder, top_k=settings.top_k,
            semantic=settings.semantic_ranker, min_reranker_score=settings.min_reranker_score)
        if settings.storage_account_url:
            from regrag.storage import BlobCorpusStore
            try:
                active = BlobCorpusStore(azure_clients.blob_container(settings)).active()
                manifest = active[0] if active else None
            except Exception as exc:  # metadata only; search keeps working
                log(f"Corpus manifest unavailable: {type(exc).__name__}")
    else:
        from regrag.ingest import ensure_local_corpus
        from regrag.storage import LocalCorpusStore
        manifest, units = ensure_local_corpus(LocalCorpusStore(settings.local_dir), log=log)
        retriever = LocalRetriever(units, min_score=settings.min_lexical_score, top_k=settings.top_k)
    generator = verifier = None
    if settings.generation_enabled:
        generator = Generator(client, settings.chat_deployment)
        if settings.verify_claims:
            verifier = ModelVerifier(client, settings.verifier_deployment or settings.chat_deployment)
    return Assistant(retriever, generator, verifier, settings.claim_policy, manifest,
                     settings.log_questions)
