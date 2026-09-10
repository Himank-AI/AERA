"""Serve the exported Next.js UI from FastAPI in production."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from config import PROJECT_ROOT

UI_DIR = PROJECT_ROOT / "frontend" / "out"

_SKIP_EXACT = {"health", "docs", "redoc", "openapi.json"}


def ui_enabled() -> bool:
    return (UI_DIR / "index.html").is_file()


def _safe_file(full_path: str) -> Path | None:
    rel = Path(full_path.strip("/"))
    if rel.is_absolute() or ".." in rel.parts:
        return None
    target = (UI_DIR / rel).resolve()
    root = UI_DIR.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if target.is_file():
        return target
    if target.is_dir() and (target / "index.html").is_file():
        return target / "index.html"
    html = Path(str(target) + ".html")
    if html.is_file():
        return html
    return None


def mount_ui(app: FastAPI) -> None:
    if not ui_enabled():
        return

    @app.get("/")
    async def ui_root() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.get("/{full_path:path}")
    async def ui_spa(full_path: str) -> FileResponse:
        if full_path in _SKIP_EXACT or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        found = _safe_file(full_path)
        if found is not None:
            return FileResponse(found)
        not_found = UI_DIR / "404.html"
        if not_found.is_file():
            return FileResponse(not_found, status_code=404)
        raise HTTPException(status_code=404, detail="Not found")
