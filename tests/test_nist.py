from types import SimpleNamespace

import pytest

from regrag.cellar import SourceError
from regrag.generation import resolve
from regrag.nist import fetch_framework, parse_framework
from regrag.retrieval import LocalRetriever
from regrag.sources import NIST_RMF_URL
from regrag.storage import LocalCorpusStore
from regrag.verification import rule_check


def pdf_reader(monkeypatch):
    text = "NIST AI 100-1 AI RMF 1.0 GOVERN MAP MEASURE MANAGE. The Framework is voluntary."
    pages = [SimpleNamespace(extract_text=lambda: text) for _ in range(48)]
    monkeypatch.setattr("regrag.nist.PdfReader", lambda *a, **k: SimpleNamespace(pages=pages))
    return pages


def test_framework_pages_retrieve_and_cite_without_legal_obligations(monkeypatch):
    pdf_reader(monkeypatch)
    units = parse_framework(b"%PDF-fixture")
    evidence = LocalRetriever(units).retrieve("voluntary Framework", "NIST_AI_RMF")
    assert evidence and evidence[0]["article"] is None
    result = resolve({"claims": [{"statement": "The Framework is voluntary.", "excerpt_id": "E1"}]},
                     {"E1": evidence[0]})
    claim = result["claims"][0]
    assert claim["citation"].startswith("NIST AI RMF 1.0 PDF page")
    assert claim["url"].startswith(NIST_RMF_URL + "#page=")
    assert claim["source_type"] == "voluntary_framework"
    assert rule_check(claim) is None
    claim["statement"] = "Organisations must comply with this framework."
    assert rule_check(claim)["support"] == "partial"


def test_partial_framework_rejected(monkeypatch):
    pages = pdf_reader(monkeypatch)
    pages.pop()
    pages[0] = SimpleNamespace(extract_text=lambda: "")
    with pytest.raises(SourceError, match="incomplete"):
        parse_framework(b"%PDF-fixture")


@pytest.mark.parametrize("status,content_type", [(302, "application/pdf"), (200, "text/html"), (500, "application/pdf")])
def test_framework_download_fails_closed(status, content_type):
    def get(url, **kwargs):
        assert url == NIST_RMF_URL and kwargs["allow_redirects"] is False
        return SimpleNamespace(status_code=status, headers={"Content-Type": content_type})
    with pytest.raises(SourceError):
        fetch_framework(get)


def test_raw_pdf_preserved_byte_for_byte(tmp_path):
    data = b"%PDF-1.7\n\xff\x00"
    path = LocalCorpusStore(tmp_path).save_raw("NIST_AI_RMF", "hash", data)
    from pathlib import Path
    assert Path(path).suffix == ".pdf"
    assert Path(path).read_bytes() == data
