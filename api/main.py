"""FastAPI app: a read-only API over run folders, plus the built front end when present.

Routes follow docs/API_CONTRACT.md. Nothing here reads runs/private, row maps, caches or keys.
Start with: uvicorn api.main:create_app --factory --port 8000
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from api import cli
from api.pipeline import io, views

log = logging.getLogger("purposefit.api")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIST = PROJECT_ROOT / "web" / "dist"
LOCAL_ORIGIN = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"


class NotReady(Exception):
    pass


class BadRequest(Exception):
    pass


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def create_app(runs_dir: Path | None = None, web_dist: Path | None = None) -> FastAPI:
    key = cli.require_hmac_key()  # refuses to start without the key
    runs = Path(runs_dir) if runs_dir else cli.runs_dir()
    app = FastAPI(title="PurposeFit", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origin_regex=LOCAL_ORIGIN, allow_methods=["GET"],
                       allow_headers=["Content-Type"])  # fmt: skip

    @app.exception_handler(views.NotFound)
    async def not_found(_r: Request, exc: views.NotFound):
        return _error(404, exc.code, exc.message)

    @app.exception_handler(views.GateFailed)
    async def gate_failed(_r: Request, exc: views.GateFailed):
        names = ", ".join(exc.blocking)
        return _error(409, "gate_failed", f"The release gate has not passed. Failing checks: {names}.")

    @app.exception_handler(RequestValidationError)
    async def bad_request(_r: Request, _exc: RequestValidationError):
        return _error(400, "bad_request", "The request is not valid.")

    def ready() -> None:
        if not (io.data_root() / "customer_service").is_dir():
            raise NotReady

    def safe_id(run_id: str) -> str:
        if not views.RUN_ID_RE.match(run_id):
            raise BadRequest("The run id may only hold letters, digits, _ and -, up to 64 characters.")
        return run_id

    @app.exception_handler(NotReady)
    async def not_ready(_r: Request, _e: Exception):
        return _error(503, "not_ready", "The proving ground data is missing.")

    @app.exception_handler(BadRequest)
    async def bad_id(_r: Request, e: Exception):
        return _error(400, "bad_request", str(e))

    @app.get("/api/health")
    def health():
        return {"status": "ok", "git_hash": cli.git_hash(), "key_id": cli.key_id(key),
                "llm": views.llm_view(),
                "proving_ground": (io.data_root() / "customer_service").is_dir()}  # fmt: skip

    @app.get("/api/scenarios")
    def scenarios():
        ready()
        return views.scenarios_view()

    @app.get("/api/leaderboard")
    def leaderboard():
        return views.leaderboard_view(runs)

    @app.post("/api/runs")
    def create_run():
        return _error(501, "not_implemented", "Starting runs from the API is not available in this build.")

    @app.get("/api/runs/{run_id}")
    def run(run_id: str):
        return views.run_view(runs, safe_id(run_id))

    @app.get("/api/runs/{run_id}/stages/{stage}")
    def stage(run_id: str, stage: str):
        safe_id(run_id)
        if stage not in views.PAYLOAD_STAGES:
            raise BadRequest("Unknown stage name.")
        return views.stage_view(runs, run_id, stage)

    @app.get("/api/runs/{run_id}/export")
    def export(run_id: str):
        data = views.export_zip(runs, safe_id(run_id))
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{run_id}_release.zip"'})  # fmt: skip

    @app.get("/api/{rest:path}")
    def unknown(rest: str):
        return _error(404, "not_found", "No such endpoint.")

    dist = Path(web_dist) if web_dist else WEB_DIST
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    log.info('{"stage": "api", "event": "ready"}')
    return app

