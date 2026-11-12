"""HTTP API and web UI served from Azure Container Apps."""
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from regrag import __version__, telemetry
from regrag.config import Settings
from regrag.sources import ACTS

STATIC = Path(__file__).resolve().parent / "static"
SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
                                "form-action 'self'; frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    act: str | None = None


class RateLimiter:
    """Sliding one-minute window per client. In-memory, so limits apply per replica."""

    def __init__(self, per_minute: int, clock=time.monotonic, max_clients: int = 10_000):
        self.per_minute = per_minute
        self.clock = clock
        self.max_clients = max_clients
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = self.clock()
        with self.lock:
            if len(self.hits) > self.max_clients:
                self.hits.clear()
            window = self.hits[client]
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return False
            window.append(now)
            return True


class DailyBudget:
    """Caps model-backed requests per UTC day and replica to bound provider cost."""

    def __init__(self, limit: int, today=lambda: datetime.now(UTC).date()):
        self.limit = limit
        self.today = today
        self.day = None
        self.used = 0
        self.lock = threading.Lock()

    def take(self) -> bool:
        with self.lock:
            today = self.today()
            if self.day != today:
                self.day, self.used = today, 0
            if self.used >= self.limit:
                return False
            self.used += 1
            return True


def client_id(request: Request) -> str:
    # Container Apps ingress appends the caller address as the last X-Forwarded-For hop;
    # earlier hops are client-controlled and ignored. Uvicorn runs without proxy_headers.
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "unknown"


def create_app(settings: Settings | None = None, assistant_factory=None) -> FastAPI:
    settings = settings or Settings.from_env()
    telemetry.configure(settings)
    if assistant_factory is None:
        from regrag.pipeline import build_assistant
        assistant_factory = build_assistant
    state: dict = {"assistant": None}
    init_lock = threading.Lock()
    limiter = RateLimiter(settings.rate_limit_per_minute)
    budget = DailyBudget(settings.daily_generation_limit)

    def assistant():
        if state["assistant"] is None:
            with init_lock:
                if state["assistant"] is None:
                    state["assistant"] = assistant_factory(settings)
        return state["assistant"]

    app = FastAPI(title="Regulatory RAG Assistant", version=__version__,
                  docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    def readyz():
        try:
            assistant()
        except Exception as exc:
            return JSONResponse({"status": "unavailable", "reason": type(exc).__name__}, status_code=503)
        return {"status": "ready"}

    @app.get("/api/info")
    def info():
        return assistant().info()

    @app.post("/api/ask")
    def ask(body: AskRequest, request: Request):
        question = body.question.strip()
        if len(question) < 3 or len(question) > settings.max_question_chars:
            raise HTTPException(422, f"Question must be 3-{settings.max_question_chars} characters")
        if body.act is not None and body.act not in ACTS:
            raise HTTPException(422, "Unknown act filter")
        if not limiter.allow(client_id(request)):
            raise HTTPException(429, "Too many requests; try again in a minute")
        current = assistant()
        if current.generator is not None and not budget.take():
            raise HTTPException(429, "Daily generation limit reached")
        try:
            return current.ask(question, body.act)
        except Exception as exc:
            # Provider, parsing and validation failures are errors, never abstentions.
            raise HTTPException(502, f"Answer could not be produced ({type(exc).__name__})") from exc

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    return app


def app_factory() -> FastAPI:
    """Entry point for `uvicorn --factory regrag.api:app_factory`."""
    return create_app()
