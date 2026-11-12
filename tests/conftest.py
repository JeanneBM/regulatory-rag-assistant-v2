"""Offline test doubles for the Publications Office, Azure OpenAI and Azure AI Search."""
import json
from types import SimpleNamespace

import pytest

from regrag.sources import ACTS, CELLAR_HOST, Act

XHTML = "application/xhtml+xml;charset=UTF-8"
BODY = "Financial entities shall maintain sound documentation of their ICT systems. "


def point_table(rows: list[tuple[str, str]], nested: dict | None = None) -> str:
    cells = []
    for marker, text in rows:
        inner = point_table(nested[marker]) if nested and marker in nested else ""
        cells.append(f"<tr><td valign='top'><p class='oj-normal'>({marker})</p></td>"
                     f"<td valign='top'><p class='oj-normal'>{text}</p>{inner}</td></tr>")
    return "<table width='100%'><col width='4%'/><col width='96%'/><tbody>" + "".join(cells) + "</tbody></table>"


def article_html(number: int, body: str | None = None, title: str | None = None) -> str:
    title = title or f"Title of article {number}"
    body = body or f"<div><p class='oj-normal'>1.   {BODY}</p></div><div><p class='oj-normal'>2.   {BODY}</p></div>"
    return (f"<div class='eli-subdivision' id='art_{number}'><p class='oj-ti-art'>Article {number}</p>"
            f"<div class='eli-title'><p class='oj-sti-art'>{title}</p></div>{body}</div>")


def act_document(count: int, overrides: dict[int, str] | None = None, chapters: bool = True) -> str:
    overrides = overrides or {}
    parts = ["<html><body><div id='document1'>",
             "<p class='oj-doc-ti'>REGULATION (EU) 2022/2554 OF THE EUROPEAN PARLIAMENT</p>",
             "<p class='oj-normal'>(1) Recital text mentioning Article 1 of another act.</p>"]
    for number in range(1, count + 1):
        if chapters and number % 10 == 1:
            parts.append(f"<p class='oj-ti-section-1'>CHAPTER {number}</p>"
                         "<p class='oj-ti-section-2'>GENERAL PROVISIONS</p>")
        parts.append(overrides.get(number) or article_html(number))
    parts.append("<p class='oj-normal'>This Regulation shall be binding in its entirety and "
                 "directly applicable in all Member States.</p>"
                 "<p class='oj-normal'>Done at Strasbourg, 14 December 2022.</p>"
                 "<p class='oj-doc-ti'>ANNEX</p><p class='oj-normal'>Annex text.</p></div></body></html>")
    return "".join(parts)


class FakeCellar:
    """303 from the CELEX resource to a plain-HTTP manifestation, then the XHTML."""

    def __init__(self, documents: dict[str, str] | None = None, status=200, location=None,
                 content_type=XHTML):
        self.documents = documents or {key: act_document(act.articles) for key, act in ACTS.items()}
        self.status, self.location, self.content_type = status, location, content_type
        self.calls = []

    @staticmethod
    def item(celex: str) -> str:
        return f"https://{CELLAR_HOST}/resource/cellar/{celex}.0006.03/DOC_1"

    def __call__(self, url, headers=None, **kwargs):
        self.calls.append(url)
        assert headers["Accept"] == "application/xhtml+xml"
        assert headers["Accept-Language"] == "eng"
        for key, html in self.documents.items():
            act = ACTS.get(key) or EXTRA_ACTS[key]
            if url == act.cellar_url:
                target = self.location or self.item(act.celex).replace("https://", "http://")
                return SimpleNamespace(status_code=303, headers={"Location": target}, text="")
            if url == self.item(act.celex):
                return SimpleNamespace(status_code=self.status, text=html,
                                       headers={"Content-Type": self.content_type})
        raise AssertionError(f"unexpected request {url}")


EXTRA_ACTS = {"NIS2": Act("NIS2", "32022L2555", 46, "NIS2", "Directive (EU) 2022/2555")}


@pytest.fixture
def cellar(monkeypatch):
    fake = FakeCellar()
    monkeypatch.setattr("regrag.cellar.requests.get", fake)
    return fake


def unit(uid="DORA-art-6-par-1", act="DORA", article="6", text=None, label=None, title="ICT risk management framework"):
    return {"id": uid, "act": act, "celex": ACTS[act].celex, "article": article,
            "article_title": title, "paragraph": "1", "point": None,
            "label": label or f"Article {article}(1)",
            "text": text or "1. Financial entities shall have a sound, comprehensive and well-documented "
                            "ICT risk management framework as part of their overall risk management system.",
            "url": ACTS[act].eurlex_url, "ordinal": 0}


def completion(content, finish_reason="stop", refusal=None, usage=(100, 20)):
    message = SimpleNamespace(content=content if isinstance(content, str) or content is None
                              else json.dumps(content), refusal=refusal)
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason, message=message)],
        usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1],
                              total_tokens=usage[0] + usage[1]))


class FakeOpenAI:
    """Replays queued chat completions and returns deterministic embeddings."""

    def __init__(self, replies=None, dimensions=4):
        self.replies = list(replies or [])
        self.requests = []
        self.embedding_requests = []
        self.dimensions = dimensions
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.embeddings = SimpleNamespace(create=self._embed)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if not self.replies:
            raise AssertionError("unexpected chat completion")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def _embed(self, model, input, dimensions=None):
        self.embedding_requests.append(list(input))
        data = [SimpleNamespace(index=i, embedding=[float(len(text) % 7), 1.0, 0.0, 0.5][:self.dimensions])
                for i, text in enumerate(input)]
        return SimpleNamespace(data=list(reversed(data)),
                               usage=SimpleNamespace(total_tokens=10 * len(input)))
