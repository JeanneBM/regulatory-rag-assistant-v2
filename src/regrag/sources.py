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
    return {**ACTS, NIST_RMF.key: NIST_RMF, **{key: spec.source for key, spec in PDF_SOURCES.items()}}


def source_url(source: Act) -> str:
    if source.key == NIST_RMF.key:
        return NIST_RMF_URL
    return PDF_SOURCES[source.key].url if source.key in PDF_SOURCES else source.eurlex_url


@dataclass(frozen=True)
class PdfSource:
    source: Act
    url: str
    pages: int
    markers: tuple[str, ...]
    sha256: str


# Fixed editions: changed bytes require explicit source review, never silent replacement.
PDF_SOURCES: dict[str, PdfSource] = {
    'NIST_GENAI': PdfSource(
        Act('NIST_GENAI', "", 0, 'NIST GenAI Profile',
            'Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile',
            'voluntary_framework', 'July 2024, NIST AI 600-1'),
        'https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf',
        64, ('NIST AI 600-1', 'Confabulation', 'GOVERN', 'MEASURE'),
        '6e73620ab6b64e90ef2c04bf0e0d6246185a2f4b1b13cab0df494496cff89b6a'),
    'GPAI_TRANSPARENCY': PdfSource(
        Act('GPAI_TRANSPARENCY', "", 0, 'GPAI Code: Transparency',
            'General-Purpose AI Code of Practice: Transparency',
            'voluntary_code', 'Final, 10 July 2025'),
        'https://ec.europa.eu/newsroom/dae/redirection/document/118120',
        6, ('Transparency Chapter', 'Signatories', 'Article 53'),
        '407e3a0a66327847a4bddb811fe619c8a588892ec451d23435d06485c20a4cf8'),
    'GPAI_COPYRIGHT': PdfSource(
        Act('GPAI_COPYRIGHT', "", 0, 'GPAI Code: Copyright',
            'General-Purpose AI Code of Practice: Copyright',
            'voluntary_code', 'Final, 10 July 2025'),
        'https://ec.europa.eu/newsroom/dae/redirection/document/118115',
        6, ('Copyright Chapter', 'Signatories', 'copyright'),
        'cdb3c117e8e51282ab61fad8af9d5cd1acaf1773a5eadce178c3d10498ca864a'),
    'GPAI_SAFETY_SECURITY': PdfSource(
        Act('GPAI_SAFETY_SECURITY', "", 0, 'GPAI Code: Safety and Security',
            'General-Purpose AI Code of Practice: Safety and Security',
            'voluntary_code', 'Final, 10 July 2025'),
        'https://ec.europa.eu/newsroom/dae/redirection/document/118119',
        43, ('Safety and Security Chapter', 'Signatories', 'systemic risk'),
        'd879f9b54c6068aae57ebaead9d90ddaa46f2503312b9185367a724fa8da2f4a'),
}
