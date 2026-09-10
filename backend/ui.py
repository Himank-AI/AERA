"""Serve the exported Next.js UI from FastAPI in production."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import PROJECT_ROOT

UI_DIR = PROJECT_ROOT / "frontend" / "out"


def ui_enabled() -> bool:
    return (UI_DIR / "index.html").is_file()


def mount_ui(app: FastAPI) -> None:
    if not ui_enabled():
        return
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
