"""Text normalisation shared by parsing, quoting and verification."""
import re
import unicodedata

QUOTE_GLYPHS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
})
NUMBER_RE = re.compile(r"\d+(?:[.,  ]\d{3})*(?:[.,]\d+)?")


def squash(text: str) -> str:
    """Collapse every run of whitespace to one space."""
    return " ".join(text.split())


def normalize(text: str) -> str:
    """Canonical form for quote matching: NFKC, straight quotes, single spaces.

    Only presentation differences are removed; wording, punctuation and word order
    must still match.
    """
    return squash(unicodedata.normalize("NFKC", text).translate(QUOTE_GLYPHS))


def numbers(text: str) -> set[str]:
    """Return the figures in a text with thousands separators removed."""
    found = set()
    for match in NUMBER_RE.findall(normalize(text)):
        digits = re.sub(r"[  ]", "", match)
        found.add(digits.rstrip(".,"))
    return found
