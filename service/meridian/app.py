"""Composition root. Load the environment, rebuild usage, then mount HTTP.

Routes do not construct the store. They read it from app.state, which
this module is the only place that fills in.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from meridian.auth import PermissionDenied
from meridian.config import environment_path, load_environment
from meridian.directory import load_directory
from meridian.http.errors import APIError, api_error, permission_denied
from meridian.http.routes import router
from meridian.ingest import build_facts
from meridian.store import Store

STATIC_DIR = Path(__file__).resolve().parent / "static"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def create_app(root: Path, env_name: str, db_path: Path) -> FastAPI:
    env = load_environment(environment_path(root, env_name))
    if env.name != env_name:
        raise ValueError("File says %s but MERIDIAN_ENV is %s" % (env.name, env_name))
    directory = load_directory(root / "starter-kit" / "data" / "directory")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db_path)
    store.init()
    store.replace_usage(build_facts(root / "starter-kit" / "data", directory))
    store.seed_capabilities(env, directory.group_ids())

    app = FastAPI(title="Meridian usage", version="1.0.0")
    app.state.env = env
    app.state.directory = directory
    app.state.store = store
    app.add_exception_handler(PermissionDenied, permission_denied)
    app.add_exception_handler(APIError, api_error)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


def app_from_env() -> FastAPI:
    root = Path(os.environ.get("MERIDIAN_ROOT", repo_root()))
    env_name = os.environ.get("MERIDIAN_ENV", "prod")
    db_path = Path(os.environ.get("MERIDIAN_DB", root / "var" / "meridian.db"))
    return create_app(root, env_name, db_path)


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app_from_env(), host=host, port=port)
