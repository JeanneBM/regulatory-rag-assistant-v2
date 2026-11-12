"""Command line: regrag ingest | ask | serve | eval | stats."""
import argparse
import json
import sys
from pathlib import Path

import requests

from regrag.config import Settings
from regrag.sources import ACTS

DEFAULT_CASES = Path(__file__).resolve().parents[2] / "eval" / "pilot.json"


def _ingest(settings: Settings, target: str) -> dict:
    from regrag import azure_clients
    from regrag.ingest import run_ingest
    if target == "local":
        from regrag.storage import LocalCorpusStore
        return run_ingest(LocalCorpusStore(settings.local_dir))
    from regrag.embeddings import AzureEmbedder
    from regrag.search_index import SearchPublisher
    from regrag.storage import BlobCorpusStore
    missing = [n for n, v in {"AZURE_STORAGE_ACCOUNT_URL": settings.storage_account_url,
                              "AZURE_SEARCH_ENDPOINT": settings.search_endpoint,
                              "AZURE_OPENAI_ENDPOINT": settings.openai_endpoint,
                              "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": settings.embedding_deployment}.items() if not v]
    if missing:
        raise ValueError("Azure ingest needs " + ", ".join(missing))
    embedder = AzureEmbedder(azure_clients.openai_client(settings), settings.embedding_deployment,
                             settings.embedding_dimensions)
    publisher = SearchPublisher(azure_clients.search_index_client(settings), embedder,
                                alias=settings.search_alias, prefix=settings.search_index_prefix,
                                dimensions=settings.embedding_dimensions,
                                semantic=settings.semantic_ranker)
    return run_ingest(BlobCorpusStore(azure_clients.blob_container(settings)), publisher)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="regrag", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Import the acts from the EU Publications Office")
    ingest.add_argument("--target", choices=["local", "azure"], default="local")
    ask = commands.add_parser("ask", help="Ask one question")
    ask.add_argument("question")
    ask.add_argument("--act", choices=list(ACTS))
    serve = commands.add_parser("serve", help="Run the web UI and API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    evaluate = commands.add_parser("eval", help="Run the pilot question set")
    evaluate.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    evaluate.add_argument("--retrieval-only", action="store_true", help="Skip all model calls")
    evaluate.add_argument("--output", type=Path, default=None)
    commands.add_parser("stats", help="Print structural statistics of the local corpus")
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        if args.command == "ingest":
            from regrag.telemetry import configure
            configure(settings)
            manifest = _ingest(settings, args.target)
            print(json.dumps({k: manifest[k] for k in ("corpus_sha256", "units", "fetched_at")}
                             | {"search": manifest.get("search")}, indent=2))
        elif args.command == "ask":
            from regrag.pipeline import build_assistant
            result = build_assistant(settings, log=lambda m: print(m, file=sys.stderr)).ask(
                args.question, args.act)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "serve":
            import uvicorn

            from regrag.api import create_app
            uvicorn.run(create_app(settings), host=args.host, port=args.port,
                        proxy_headers=False, server_header=False)
        elif args.command == "eval":
            from regrag.evaluation import load_cases, run
            from regrag.pipeline import build_assistant
            assistant = build_assistant(settings)
            if not args.retrieval_only and assistant.generator is None:
                raise ValueError("Full evaluation needs AZURE_OPENAI_ENDPOINT and "
                                 "AZURE_OPENAI_CHAT_DEPLOYMENT (or use --retrieval-only)")
            report, code = run(assistant, load_cases(args.cases), args.retrieval_only,
                               args.output or settings.local_dir / "eval")
            print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
            print("Reports: " + ", ".join(report["files"]))
            return code
        elif args.command == "stats":
            from regrag.parser import corpus_stats
            from regrag.storage import LocalCorpusStore
            active = LocalCorpusStore(settings.local_dir).active()
            if not active:
                raise ValueError("No local corpus; run `regrag ingest` first")
            print(json.dumps({"manifest": active[0], "stats": corpus_stats(active[1])}, indent=2))
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
