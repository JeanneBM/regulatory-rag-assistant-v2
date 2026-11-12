import pytest
from fastapi.testclient import TestClient

from conftest import unit
from regrag.api import DailyBudget, RateLimiter, create_app
from regrag.config import Settings
from regrag.pipeline import Assistant
from regrag.retrieval import LocalRetriever


class Exploding:
    def __init__(self, retriever):
        self.retriever = retriever
        self.generator = object()
        self.manifest = None

    def ask(self, question, act=None):
        raise RuntimeError("provider down: secret detail")


def client(settings=None, factory=None):
    settings = settings or Settings(rate_limit_per_minute=100)
    factory = factory or (lambda s: Assistant(LocalRetriever([unit()]), manifest={"corpus_sha256": "abc"}))
    return TestClient(create_app(settings, factory))


def test_health_info_and_static_ui_with_security_headers():
    api = client()
    assert api.get("/healthz").json()["status"] == "ok"
    assert api.get("/readyz").json() == {"status": "ready"}
    info = api.get("/api/info").json()
    assert info["backend"] == "local-tfidf" and info["corpus"]["corpus_sha256"] == "abc"
    page = api.get("/")
    assert page.status_code == 200 and "Regulatory RAG Assistant" in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"] == "nosniff"
    assert api.get("/static/app.js").status_code == 200
    assert api.get("/docs").status_code == 404


def test_ask_returns_evidence_and_rejects_invalid_input():
    api = client()
    response = api.post("/api/ask", json={"question": "ICT risk management framework", "act": "DORA"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "retrieval_only"
    assert api.post("/api/ask", json={"question": "x" * 1001}).status_code == 422
    assert api.post("/api/ask", json={"question": "valid question", "act": "GDPR"}).status_code == 422
    assert api.post("/api/ask", json={"question": "ab"}).status_code == 422


def test_rate_limit_and_daily_budget():
    api = client(Settings(rate_limit_per_minute=2))
    headers = {"x-forwarded-for": "198.51.100.7, 203.0.113.9"}
    codes = [api.post("/api/ask", json={"question": "ICT framework"}, headers=headers).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429]
    other = {"x-forwarded-for": "203.0.113.10"}
    assert api.post("/api/ask", json={"question": "ICT framework"}, headers=other).status_code == 200

    days = iter(["d1", "d1", "d2"])
    budget = DailyBudget(1, today=lambda: next(days))
    assert [budget.take(), budget.take(), budget.take()] == [True, False, True]


def test_rate_limiter_window_slides():
    now = [0.0]
    limiter = RateLimiter(1, clock=lambda: now[0])
    assert limiter.allow("a") and not limiter.allow("a")
    now[0] = 61
    assert limiter.allow("a")


def test_provider_errors_are_502_without_leaking_details():
    api = client(factory=lambda s: Exploding(LocalRetriever([unit()])))
    response = api.post("/api/ask", json={"question": "ICT framework"})
    assert response.status_code == 502
    assert "secret detail" not in response.text and "RuntimeError" in response.text


def test_readiness_fails_when_backend_cannot_start():
    def broken(settings):
        raise RuntimeError("search unreachable")
    response = client(factory=broken).get("/readyz")
    assert response.status_code == 503 and response.json()["reason"] == "RuntimeError"


@pytest.mark.parametrize("env, error", [
    ({"REGRAG_BACKEND": "azure"}, "AZURE_SEARCH_ENDPOINT"),
    ({"REGRAG_BACKEND": "cloud"}, "must be"),
    ({"REGRAG_CLAIM_POLICY": "loose"}, "CLAIM_POLICY"),
])
def test_settings_validation(monkeypatch, env, error):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=error):
        Settings.from_env()
