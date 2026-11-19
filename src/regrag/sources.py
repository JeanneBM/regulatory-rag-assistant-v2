"""Registry of the legal acts the assistant imports.

Adding an act means adding its CELEX number and the number of articles the import
must cover. The importer fails closed when any article is missing.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Act:
    key: str
    celex: str
    articles: int
    short_name: str
    title: str

    source_type: str = "eu_regulation"
    version: str = "original published act"

    @property
    def eurlex_url(self) -> str:
        return EURLEX_URL.format(celex=self.celex)

    @property
    def cellar_url(self) -> str:
        return CELLAR_URL.format(celex=self.celex)


# Human-readable citation links. EUR-Lex answers scripts with an AWS WAF challenge
# (HTTP 202), so the text itself is downloaded from the Publications Office Cellar.
EURLEX_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}"
CELLAR_URL = "https://publications.europa.eu/resource/celex/{celex}"
CELLAR_HOST = "publications.europa.eu"

ACTS: dict[str, Act] = {
    "AI_ACT": Act(
        key="AI_ACT", celex="32024R1689", articles=113, short_name="AI Act",
        title="Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence",
    ),
    "DORA": Act(
        key="DORA", celex="32022R2554", articles=64, short_name="DORA",
        title="Regulation (EU) 2022/2554 on digital operational resilience for the financial sector",
    ),
}

NIST_RMF = Act("NIST_AI_RMF", "", 0, "NIST AI RMF 1.0",
               "Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
               "voluntary_framework", "1.0 (January 2023), NIST AI 100-1")
NIST_RMF_URL = "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf"


def all_sources() -> dict[str, Act]:
    return {**ACTS, NIST_RMF.key: NIST_RMF}


def source_url(source: Act) -> str:
    return NIST_RMF_URL if source.key == NIST_RMF.key else source.eurlex_url
