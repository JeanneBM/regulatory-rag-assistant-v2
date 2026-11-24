import hashlib
from dataclasses import replace
from types import SimpleNamespace

import pytest

from regrag.cellar import SourceError
from regrag.pdf_sources import fetch_pdf_source, parse_pdf_source
from regrag.sources import PDF_SOURCES
from regrag.verification import rule_check


@pytest.mark.parametrize("key", list(PDF_SOURCES))
def test_pinned_pdf_units_keep_source_and_original_page_links(monkeypatch, key):
    spec = PDF_SOURCES[key]
    data = b"%PDF-fixture"
    spec = replace(spec, sha256=hashlib.sha256(data).hexdigest())
    text = " ".join(spec.markers)
    pages = [SimpleNamespace(extract_text=lambda: text) for _ in range(spec.pages)]
    monkeypatch.setattr("regrag.pdf_sources.PdfReader", lambda *a, **k: SimpleNamespace(pages=pages))
    units = parse_pdf_source(data, spec)
    assert len(units) == spec.pages
    assert units[-1]["id"] == f"{key}-page-{spec.pages}-part-1"
    assert units[-1]["url"] == f"{spec.url}#page={spec.pages}"
    assert units[0]["source_type"] == spec.source.source_type
    assert units[0]["source_sha256"] == spec.sha256
    assert units[0]["article"] is None
    pages.pop()
    with pytest.raises(SourceError, match="incomplete"):
        parse_pdf_source(data, spec)


def test_changed_pdf_bytes_are_rejected_before_parsing():
    with pytest.raises(SourceError, match="PDF changed"):
        parse_pdf_source(b"%PDF-new-edition", PDF_SOURCES["NIST_GENAI"])


@pytest.mark.parametrize("status,content_type,chunks", [
    (302, "application/pdf", []), (200, "text/html", []),
    (200, "application/pdf", [b"not a PDF"]),
])
def test_download_rejects_redirects_wrong_type_and_non_pdf(status, content_type, chunks):
    closed = []

    def get(url, **kwargs):
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        return SimpleNamespace(status_code=status, headers={"Content-Type": content_type},
                               iter_content=lambda **k: iter(chunks), close=lambda: closed.append(True))
    with pytest.raises(SourceError):
        fetch_pdf_source(PDF_SOURCES["NIST_GENAI"], get)
    assert closed == [True]


def test_download_stops_at_size_limit_and_closes_response(monkeypatch):
    monkeypatch.setattr("regrag.pdf_sources.MAX_BYTES", 5)
    consumed, closed = [], []

    def chunks(**kwargs):
        for chunk in [b"%PDF-", b"too large", b"must not be read"]:
            consumed.append(chunk)
            yield chunk

    def get(url, **kwargs):
        return SimpleNamespace(status_code=200, headers={"Content-Type": "application/pdf"},
                               iter_content=chunks, close=lambda: closed.append(True))
    with pytest.raises(SourceError, match="too large"):
        fetch_pdf_source(PDF_SOURCES["NIST_GENAI"], get)
    assert len(consumed) == 2 and closed == [True]


def test_genai_guidance_cannot_be_promoted_to_legal_duty():
    claim = {"act": "NIST_GENAI", "statement": "Organisations must comply with this framework.",
             "quote": "This voluntary profile suggests risk management actions."}
    assert rule_check(claim)["support"] == "partial"


def test_unicode_ligatures_are_normalised_for_retrieval(monkeypatch):
    spec = replace(PDF_SOURCES["NIST_GENAI"], pages=1, markers=("Confabulation",),
                   sha256=hashlib.sha256(b"%PDF-fixture").hexdigest())
    page = SimpleNamespace(extract_text=lambda: "Conﬁdently stated confabulation.")
    monkeypatch.setattr("regrag.pdf_sources.PdfReader", lambda *a, **k: SimpleNamespace(pages=[page]))
    assert "Confidently" in parse_pdf_source(b"%PDF-fixture", spec)[0]["text"]
