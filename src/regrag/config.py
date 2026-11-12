"""Runtime settings, read from environment variables only.

No secrets are required for the Azure backend: every Azure call authenticates with
Microsoft Entra ID (`az login` locally).
"""
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LOCAL_DIR = Path.cwd() / ".local"


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _number(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    backend: str = "local"                      # local | azure
    local_dir: Path = DEFAULT_LOCAL_DIR

    openai_endpoint: str = ""
    openai_api_version: str = "2024-10-21"
    openai_api_key: str = ""                    # optional; Entra ID is preferred
    chat_deployment: str = ""
    verifier_deployment: str = ""
    embedding_deployment: str = ""
    embedding_dimensions: int = 1536

    search_endpoint: str = ""
    search_alias: str = "regrag"
    search_index_prefix: str = "regrag"
    semantic_ranker: bool = True
    min_reranker_score: float = 1.2             # provisional; calibrate with `regrag eval`
    min_lexical_score: float = 0.05             # provisional; local TF-IDF backend

    storage_account_url: str = ""
    storage_container: str = "corpus"

    top_k: int = 8
    verify_claims: bool = True
    claim_policy: str = "strict"                # strict: supported only | lenient: + partial


    @property
    def generation_enabled(self) -> bool:
        return bool(self.openai_endpoint and self.chat_deployment)

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            backend=os.getenv("REGRAG_BACKEND", "local").strip().lower(),
            local_dir=Path(os.getenv("REGRAG_LOCAL_DIR") or DEFAULT_LOCAL_DIR),
            openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-10-21",
            openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            chat_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
            verifier_deployment=os.getenv("AZURE_OPENAI_VERIFIER_DEPLOYMENT", ""),
            embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", ""),
            embedding_dimensions=int(_number("AZURE_OPENAI_EMBEDDING_DIMENSIONS", 1536)),
            search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT", ""),
            search_alias=os.getenv("AZURE_SEARCH_ALIAS") or "regrag",
            search_index_prefix=os.getenv("AZURE_SEARCH_INDEX_PREFIX") or "regrag",
            semantic_ranker=_flag("AZURE_SEARCH_SEMANTIC_RANKER", True),
            min_reranker_score=_number("REGRAG_MIN_RERANKER_SCORE", 1.2),
            min_lexical_score=_number("REGRAG_MIN_LEXICAL_SCORE", 0.05),
            storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL", ""),
            storage_container=os.getenv("AZURE_STORAGE_CONTAINER") or "corpus",
            top_k=int(_number("REGRAG_TOP_K", 8)),
            verify_claims=_flag("REGRAG_VERIFY_CLAIMS", True),
            claim_policy=os.getenv("REGRAG_CLAIM_POLICY", "strict").strip().lower(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.backend not in {"local", "azure"}:
            raise ValueError("REGRAG_BACKEND must be 'local' or 'azure'")
        if self.claim_policy not in {"strict", "lenient"}:
            raise ValueError("REGRAG_CLAIM_POLICY must be 'strict' or 'lenient'")
        if not 1 <= self.top_k <= 20:
            raise ValueError("REGRAG_TOP_K must be between 1 and 20")
        if self.backend == "azure":
            missing = [name for name, value in {
                "AZURE_SEARCH_ENDPOINT": self.search_endpoint,
                "AZURE_OPENAI_ENDPOINT": self.openai_endpoint,
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": self.embedding_deployment,
            }.items() if not value]
            if missing:
                raise ValueError("Azure backend needs " + ", ".join(missing))
