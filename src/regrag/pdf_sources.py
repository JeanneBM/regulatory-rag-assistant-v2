"""Pinned official AI guidance PDFs, with citations to original viewer pages."""
import hashlib
import unicodedata
from io import BytesIO

import requests
from pypdf import PdfReader

from regrag.cellar import MAX_BYTES, USER_AGENT, SourceDocument, SourceError
from regrag.parser import _split
from regrag.sources import PdfSource


def parse_pdf_source(data: bytes, spec: PdfSource) -> list[dict]:
    digest = hashlib.sha256(data).hexdigest()
    if digest != spec.sha256:
        raise SourceError(f"{spec.source.key}: PDF changed; review the pinned edition before importing")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        pages = [unicodedata.normalize("NFKC", page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise SourceError(f"{spec.source.key}: invalid or unreadable PDF") from exc
    full = " ".join(" ".join(pages).split()).casefold()
    if len(pages) != spec.pages or any(not page.strip() for page in pages) or not all(
        marker.casefold() in full for marker in spec.markers
    ):
        raise SourceError(f"{spec.source.key}: unexpected edition or incomplete PDF text")
    units = []
    for page, text in enumerate(pages, 1):
        for part, lines in enumerate(_split(text.splitlines()), 1):
            units.append({
                "id": f"{spec.source.key}-page-{page}-part-{part}", "act": spec.source.key,
                "celex": None, "article": None, "paragraph": None, "point": None,
                "article_title": spec.source.title, "label": f"PDF page {page}, part {part}",
                "text": "\n".join(lines), "url": f"{spec.url}#page={page}", "ordinal": len(units),
                "language": "EN", "version": spec.source.version, "source_type": spec.source.source_type,
                "source_sha256": digest, "fetched_from": spec.url,
            })
    return units


def fetch_pdf_source(spec: PdfSource, get=None):
    get = get or requests.get
    # Fixed official URLs only. Do not follow redirects to an unreviewed document or host.
    response = get(spec.url, headers={"Accept": "application/pdf", "User-Agent": USER_AGENT},
                   timeout=(10, 120), allow_redirects=False, stream=True)
    try:
        if response.status_code != 200:
            raise SourceError(f"{spec.source.key}: expected HTTP 200 without redirects")
        # The Commission endpoint sends a nonstandard MIME type. Signature and the
        # reviewed SHA-256 pin authenticate the exact PDF bytes, not this header.
        chunks, size = [], 0
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise SourceError(f"{spec.source.key}: download too large")
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data.startswith(b"%PDF-"):
            raise SourceError(f"{spec.source.key}: invalid PDF")
    finally:
        response.close()
    units = parse_pdf_source(data, spec)
    return SourceDocument(spec.source, data, spec.url, hashlib.sha256(data).hexdigest()), units
