"""Corpus snapshots: raw official XHTML, parsed units and the active manifest.

Raw sources and parsed corpora are content-addressed and never overwritten, so every
indexed unit can be traced back to the exact bytes downloaded from the Publications
Office. `active.json` names the corpus the application serves.
"""
import json
from pathlib import Path
from typing import Protocol


class CorpusStore(Protocol):
    def save_raw(self, celex: str, sha256: str, html: str) -> str: ...
    def save_corpus(self, manifest: dict, units: list[dict]) -> str: ...
    def activate(self, manifest: dict) -> None: ...
    def active(self) -> tuple[dict, list[dict]] | None: ...


def raw_name(celex: str, sha256: str) -> str:
    return f"raw/{celex}/{sha256}.xhtml"


def corpus_name(digest: str) -> str:
    return f"corpus/{digest}.json"


class LocalCorpusStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _write(self, name: str, data: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(data, encoding="utf-8")
        temporary.replace(path)
        return path

    def save_raw(self, celex, sha256, html):
        path = self.root / raw_name(celex, sha256)
        if not path.exists():
            self._write(raw_name(celex, sha256), html)
        return str(path)

    def save_corpus(self, manifest, units):
        name = corpus_name(manifest["corpus_sha256"])
        return str(self._write(name, json.dumps({"manifest": manifest, "units": units},
                                                ensure_ascii=False)))

    def activate(self, manifest):
        self._write("active.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    def active(self):
        pointer = self.root / "active.json"
        if not pointer.exists():
            return None
        manifest = json.loads(pointer.read_text(encoding="utf-8"))
        corpus = self.root / corpus_name(manifest["corpus_sha256"])
        if not corpus.exists():
            return None
        payload = json.loads(corpus.read_text(encoding="utf-8"))
        return manifest, payload["units"]


class BlobCorpusStore:
    """Azure Blob Storage store, accessed with the job's managed identity."""

    def __init__(self, container_client):
        self.container = container_client

    def _exists(self, name: str) -> bool:
        return self.container.get_blob_client(name).exists()

    def _upload(self, name: str, data: str, content_type: str, overwrite: bool) -> None:
        from azure.storage.blob import ContentSettings
        self.container.upload_blob(name, data.encode("utf-8"), overwrite=overwrite,
                                   content_settings=ContentSettings(content_type=content_type))

    def save_raw(self, celex, sha256, html):
        name = raw_name(celex, sha256)
        if not self._exists(name):
            self._upload(name, html, "application/xhtml+xml; charset=utf-8", overwrite=False)
        return f"{self.container.url}/{name}"

    def save_corpus(self, manifest, units):
        name = corpus_name(manifest["corpus_sha256"])
        if not self._exists(name):
            payload = json.dumps({"manifest": manifest, "units": units}, ensure_ascii=False)
            self._upload(name, payload, "application/json", overwrite=False)
        return f"{self.container.url}/{name}"

    def activate(self, manifest):
        self._upload("active.json", json.dumps(manifest, ensure_ascii=False, indent=2),
                     "application/json", overwrite=True)

    def active_manifest(self) -> dict | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return json.loads(self.container.download_blob("active.json").readall())
        except ResourceNotFoundError:
            return None

    def active(self):
        manifest = self.active_manifest()
        if manifest is None:
            return None
        name = corpus_name(manifest["corpus_sha256"])
        if not self._exists(name):
            return None
        payload = json.loads(self.container.download_blob(name).readall())
        return manifest, payload["units"]

    def save_report(self, name: str, report: dict) -> str:
        blob = f"eval/{name}"
        self._upload(blob, json.dumps(report, ensure_ascii=False, indent=2),
                     "application/json", overwrite=False)
        return f"{self.container.url}/{blob}"
