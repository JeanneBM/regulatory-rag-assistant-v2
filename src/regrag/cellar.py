"""Download official act texts from the EU Publications Office (Cellar)."""
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from regrag.sources import CELLAR_HOST, Act

USER_AGENT = "regulatory-rag-assistant-v2 (+https://github.com/JeanneBM/regulatory-rag-assistant-v2)"
MAX_BYTES = 25 * 1024 * 1024
REDIRECTS = {301, 302, 303, 307, 308}


class SourceError(RuntimeError):
    """The official source could not be downloaded or failed validation."""


@dataclass(frozen=True)
class SourceDocument:
    act: Act
    html: str
    fetched_from: str
    sha256: str


def fetch_act(act: Act, get: Callable[..., requests.Response] | None = None) -> SourceDocument:
    """Fetch the English XHTML manifestation of an original act.

    Content negotiation on the CELEX resource answers 303 with the manifestation.
    Cellar redirects to plain HTTP, so every hop is upgraded to HTTPS and must stay
    on the Publications Office host. Any other status, host or content type fails.
    """
    get = get or requests.get
    url = act.cellar_url
    headers = {"Accept": "application/xhtml+xml", "Accept-Language": "eng",
               "User-Agent": USER_AGENT}
    for _ in range(6):
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or parts.netloc != CELLAR_HOST:
            raise SourceError(f"{act.celex}: redirect outside {CELLAR_HOST}: {url}")
        url = urlunsplit(("https", *parts[1:]))
        response = get(url, headers=headers, timeout=(10, 120), allow_redirects=False)
        if response.status_code in REDIRECTS and response.headers.get("Location"):
            url = urljoin(url, response.headers["Location"])
            continue
        if response.status_code != 200:
            raise SourceError(f"{act.celex}: HTTP {response.status_code} from {url}")
        if "html" not in response.headers.get("Content-Type", ""):
            raise SourceError(f"{act.celex}: unexpected content type from {url}")
        html = response.text
        if len(html.encode()) > MAX_BYTES:
            raise SourceError(f"{act.celex}: response larger than {MAX_BYTES} bytes")
        digest = hashlib.sha256(html.encode()).hexdigest()
        return SourceDocument(act=act, html=html, fetched_from=url, sha256=digest)
    raise SourceError(f"{act.celex}: too many redirects")
