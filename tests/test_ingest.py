import json
from unittest.mock import Mock

import pytest
from azure.core.exceptions import ResourceNotFoundError

from conftest import EXTRA_ACTS, FakeCellar, act_document
from regrag import ingest
from regrag.cellar import SourceError, fetch_act
from regrag.parser import ParseError
from regrag.sources import ACTS, CELLAR_HOST
from regrag.storage import BlobCorpusStore, LocalCorpusStore


def test_fetch_upgrades_cellar_redirects_to_https(cellar):
    document = fetch_act(ACTS["DORA"])
    assert all(call.startswith(f"https://{CELLAR_HOST}/") for call in cellar.calls)
    assert document.fetched_from == FakeCellar.item("32022R2554")
    assert len(document.sha256) == 64


@pytest.mark.parametrize("fake, error", [
    (FakeCellar(location="https://example.com/DOC_1"), "redirect outside"),
    (FakeCellar(status=202), "HTTP 202"),
    (FakeCellar(content_type="application/pdf"), "content type"),
])
def test_fetch_fails_closed(monkeypatch, fake, error):
    monkeypatch.setattr("regrag.cellar.requests.get", fake)
    with pytest.raises(SourceError, match=error):
        fetch_act(ACTS["DORA"])


def test_ingest_stores_raw_sources_corpus_and_manifest(cellar, tmp_path):
    store = LocalCorpusStore(tmp_path)
    manifest = ingest.run_ingest(store, log=lambda _: None)
    assert manifest["units"] == 2 * (113 + 64)
    assert set(manifest["acts"]) == {"AI_ACT", "DORA"}
    dora = manifest["acts"]["DORA"]
    assert dora["fetched_from"] == FakeCellar.item("32022R2554")
    assert (tmp_path / "raw" / "32022R2554" / f"{dora['source_sha256']}.xhtml").exists()
    active_manifest, units = store.active()
    assert active_manifest["corpus_sha256"] == manifest["corpus_sha256"]
    assert units[0]["source_sha256"] and units[0]["version"] == "original published act"
    assert all("fetched_at" not in u for u in units)


def test_corpus_digest_ignores_fetch_time(cellar, tmp_path):
    first = ingest.run_ingest(LocalCorpusStore(tmp_path / "a"), log=lambda _: None)
    second = ingest.run_ingest(LocalCorpusStore(tmp_path / "b"), log=lambda _: None)
    assert first["corpus_sha256"] == second["corpus_sha256"]


def test_blob_manifest_downloads_only_the_active_pointer():
    container = Mock()
    manifest = {"corpus_sha256": "example"}
    container.download_blob.return_value.readall.return_value = json.dumps(manifest).encode()
    store = BlobCorpusStore(container)

    assert store.active_manifest() == manifest
    container.download_blob.assert_called_once_with("active.json")
    container.get_blob_client.assert_not_called()

    container.download_blob.side_effect = ResourceNotFoundError("missing pointer")
    assert store.active_manifest() is None


def test_failed_import_keeps_previous_corpus(monkeypatch, cellar, tmp_path):
    store = LocalCorpusStore(tmp_path)
    previous = ingest.run_ingest(store, log=lambda _: None)
    cellar.documents["DORA"] = act_document(63)
    with pytest.raises(ParseError, match="DORA: incomplete article coverage"):
        ingest.run_ingest(store, log=lambda _: None)
    assert store.active()[0]["corpus_sha256"] == previous["corpus_sha256"]


def test_failed_indexing_does_not_activate_corpus(cellar, tmp_path):
    class Broken:
        def publish(self, units, digest):
            raise RuntimeError("search unavailable")

    store = LocalCorpusStore(tmp_path)
    with pytest.raises(RuntimeError, match="search unavailable"):
        ingest.run_ingest(store, publisher=Broken(), log=lambda _: None)
    assert store.active() is None


def test_first_use_imports_once_and_new_acts_join_automatically(monkeypatch, cellar, tmp_path):
    store = LocalCorpusStore(tmp_path)
    _, units = ingest.ensure_local_corpus(store, log=lambda _: None)
    calls = len(cellar.calls)
    assert len(ingest.ensure_local_corpus(store, log=lambda _: None)[1]) == len(units)
    assert len(cellar.calls) == calls  # stored corpus re-used

    monkeypatch.setitem(ACTS, "NIS2", EXTRA_ACTS["NIS2"])
    cellar.documents["NIS2"] = act_document(46)
    manifest, units = ingest.ensure_local_corpus(store, log=lambda _: None)
    assert {u["act"] for u in units} == {"AI_ACT", "DORA", "NIS2"}
    assert len(cellar.calls) > calls
    assert json.loads((tmp_path / "active.json").read_text())["acts"]["NIS2"]["celex"] == "32022L2555"
