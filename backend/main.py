"""AERA Motor Copilot — shared Motor + HMI + AERA runtime."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import hub, router, seed_baseline, sim_loop, ws_aera
from config import settings
from engine.pipeline import engine
from engine.simulator import motor_sim
from ui import mount_ui


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    seed_baseline()
    motor = motor_sim.as_motor()
    engine.evaluate(motor, motor_sim.as_telemetry())
    loop_task = asyncio.create_task(sim_loop())
    try:
        yield
    finally:
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AERA Motor Copilot",
    description="Industrial AI copilot with a live motor and HMI on a shared real-time state.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.add_api_websocket_route("/ws/aera", ws_aera)
mount_ui(app)


@app.get("/health")
def root_health() -> dict:
    return {
        "status": "ok",
        "service": "aera-motor-copilot",
        "motor_mode": motor_sim.mode,
    }
