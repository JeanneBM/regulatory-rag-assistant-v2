"""Import the versioned official NIST AI RMF PDF as page-addressable evidence."""
import hashlib
import unicodedata
from io import BytesIO

import requests
from pypdf import PdfReader

from regrag.cellar import MAX_BYTES, USER_AGENT, SourceDocument, SourceError
from regrag.parser import _split
from regrag.sources import NIST_RMF, NIST_RMF_URL


def parse_framework(data: bytes) -> list[dict]:
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        pages = [unicodedata.normalize("NFKC", page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise SourceError("NIST AI RMF: invalid or unreadable PDF") from exc
    full = " ".join(pages).upper()
    if len(pages) != 48 or not all(word in full for word in (
        "AI RMF 1.0", "NIST AI 100-1", "GOVERN", "MAP", "MEASURE", "MANAGE", "VOLUNTARY"
    )) or any(not page.strip() for page in pages):
        raise SourceError("NIST AI RMF: unexpected version or incomplete PDF text")
    digest = hashlib.sha256(data).hexdigest()
    units = []
    for page, text in enumerate(pages, 1):
        for part, lines in enumerate(_split(text.splitlines()), 1):
            units.append({
                "id": f"NIST_AI_RMF-page-{page}-part-{part}", "act": NIST_RMF.key,
                "celex": None, "article": None, "paragraph": None, "point": None,
                "article_title": NIST_RMF.title, "label": f"PDF page {page}, part {part}",
                "text": "\n".join(lines), "url": f"{NIST_RMF_URL}#page={page}",
                "ordinal": len(units), "language": "EN", "version": NIST_RMF.version,
                "source_type": NIST_RMF.source_type, "source_sha256": digest,
                "fetched_from": NIST_RMF_URL,
            })
    return units


def fetch_framework(get=None):
    get = get or requests.get
    response = get(NIST_RMF_URL, headers={"Accept": "application/pdf", "User-Agent": USER_AGENT},
                   timeout=(10, 120), allow_redirects=False, stream=True)
    try:
        if response.status_code != 200 or "application/pdf" not in response.headers.get("Content-Type", "").lower():
            raise SourceError("NIST AI RMF: expected HTTP 200 and application/pdf without redirects")
        chunks, size = [], 0
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise SourceError("NIST AI RMF: download too large")
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data.startswith(b"%PDF-"):
            raise SourceError("NIST AI RMF: invalid PDF")
    finally:
        response.close()
    units = parse_framework(data)
    return SourceDocument(NIST_RMF, data, NIST_RMF_URL, hashlib.sha256(data).hexdigest()), units
