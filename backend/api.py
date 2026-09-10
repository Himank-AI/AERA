"""AERA HTTP + WebSocket surface. Motor, HMI, and AERA share one runtime."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from engine.copilot import answer
from engine.events import event_log
from engine.pipeline import engine
from engine.recommend import apply_side_effect, respond
from engine.simulator import motor_sim
from engine.whatif import estimate
from knowledge.expert import EXPERT_CASES, SOPS
from knowledge.history_data import HISTORY_EVENTS, history_resolutions
from knowledge.motor import MOTOR_IDENTITY, PARAMETERS, parameter_brief
from store import learning_store

router = APIRouter()


class Hub:
    def __init__(self) -> None:
        self.connections = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.connections.discard(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        stale = []
        for ws in list(self.connections):
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


hub = Hub()


class ChatIn(BaseModel):
    message: str
    experience_level: Optional[str] = None


class FeedbackIn(BaseModel):
    feedback_type: str
    comment: str = ""
    helpful: Optional[bool] = None
    correct: Optional[bool] = None
    recommended_action_correct: Optional[bool] = None
    situation: str = ""
    risk_level: str = ""


class OutcomeIn(BaseModel):
    recommendation: str = ""
    operator_action: str = ""
    actual_cause: str = ""
    actual_solution: str = ""
    outcome: str = ""
    situation: str = ""
    risk_level: str = ""


class ExpertIn(BaseModel):
    problem: str
    symptoms: List[str] = Field(default_factory=list)
    cause: str = ""
    diagnostic_process: List[str] = Field(default_factory=list)
    solution: str = ""
    warnings: List[str] = Field(default_factory=list)
    outcome: str = ""
    notes: str = ""
    source: str = "Operator"
    pattern_family: str = ""


class ExperienceIn(BaseModel):
    experience_level: str


class ParameterIn(BaseModel):
    name: str
    value: float


class ScenarioIn(BaseModel):
    scenario: str


class RecommendIn(BaseModel):
    action: str
    message: str = ""


class WhatIfIn(BaseModel):
    message: str = ""
    load: Optional[float] = None
    speed: Optional[float] = None
    voltage: Optional[float] = None
    frequency: Optional[float] = None
    cooling: Optional[float] = None
    duration_min: Optional[float] = None
    stopped: Optional[bool] = None
    abrupt: Optional[bool] = None


@router.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "aera-motor-copilot",
        "runtime": "shared",
        "motor_mode": motor_sim.mode,
        "fabricates_data": False,
    }


@router.get("/state")
def state() -> Dict[str, Any]:
    return engine.latest or engine._disconnected()


@router.get("/motor")
def motor() -> Dict[str, Any]:
    latest = engine.latest or {}
    return {
        "identity": MOTOR_IDENTITY,
        "live": latest.get("motor") or motor_sim.as_motor(),
        "sensors": latest.get("sensors") or motor_sim.values,
        "connected": True,
    }


@router.get("/knowledge/parameters")
def parameters() -> Dict[str, Any]:
    return {key: parameter_brief(key) for key in PARAMETERS}


@router.get("/knowledge/parameters/{name}")
def one_parameter(name: str) -> Dict[str, Any]:
    if name not in PARAMETERS:
        raise HTTPException(404, "Unknown parameter")
    return parameter_brief(name)


@router.get("/knowledge/sops")
def sops() -> List[Dict[str, Any]]:
    remote = []
    return remote or SOPS


@router.get("/knowledge/expert")
def expert() -> List[Dict[str, Any]]:
    return EXPERT_CASES + (learning_store.data.get("expert") or [])


@router.post("/knowledge/expert")
def add_expert(body: ExpertIn) -> Dict[str, Any]:
    payload = body.model_dump()
    payload["source_type"] = "expert"
    payload["verified"] = True
    return learning_store.add_expert(payload)


@router.get("/history")
def history() -> Dict[str, Any]:
    latest = engine.latest or {}
    return {
        "similar": latest.get("similar") or {},
        "motor_history": HISTORY_EVENTS,
        "incidents": HISTORY_EVENTS,
        "actions": [row for row in event_log.all() if row.get("source") == "OPERATOR"],
        "resolutions": history_resolutions(),
        "learned": learning_store.data.get("incidents") or [],
    }


@router.get("/history/replay/{event_number}")
def replay(event_number: int) -> Dict[str, Any]:
    return engine.replay_for_event(event_number)


@router.get("/history/replay/live")
def replay_live() -> Dict[str, Any]:
    latest = engine.latest or {}
    return {
        "title": (latest.get("situation") or {}).get("title"),
        "timeline": latest.get("timeline") or [],
        "source": "aera-live-observation",
        "note": "This timeline is built from live Motor 01 samples as AERA observed them.",
    }


@router.post("/copilot/chat")
def chat(body: ChatIn) -> Dict[str, Any]:
    if body.experience_level:
        engine.experience_level = body.experience_level.upper()
        if engine.latest:
            engine.latest["experience_level"] = engine.experience_level
    return answer(body.message, engine.latest or {}, engine.experience_level)


@router.post("/what-if")
def what_if(body: WhatIfIn) -> Dict[str, Any]:
    hypo = {
        key: value
        for key, value in body.model_dump().items()
        if key != "message" and value is not None
    }
    return estimate(engine.latest or {}, hypothesis=hypo or None, question=body.message)


@router.post("/feedback")
def feedback(body: FeedbackIn) -> Dict[str, Any]:
    return learning_store.add_feedback(body.model_dump())


@router.post("/outcomes")
def outcomes(body: OutcomeIn) -> Dict[str, Any]:
    row = learning_store.add_outcome(body.model_dump())
    learning_store.add_incident(
        {
            "incident": body.situation or (engine.latest or {}).get("situation", {}).get("title"),
            "symptoms": (engine.latest or {}).get("narrative"),
            "aera_assessment": (engine.latest or {}).get("risk"),
            "operator_response": body.operator_action,
            "actual_root_cause": body.actual_cause,
            "solution": body.actual_solution,
            "outcome": body.outcome,
        }
    )
    return row


@router.get("/learning")
def learning() -> Dict[str, Any]:
    return {
        "feedback": learning_store.data.get("feedback") or [],
        "outcomes": learning_store.data.get("outcomes") or [],
        "incidents": learning_store.data.get("incidents") or [],
        "expert": learning_store.data.get("expert") or [],
    }


@router.post("/experience")
def set_experience(body: ExperienceIn) -> Dict[str, Any]:
    engine.experience_level = body.experience_level.upper()
    if engine.latest:
        engine.latest["experience_level"] = engine.experience_level
    return {"experience_level": engine.experience_level}


@router.get("/events")
def events() -> Dict[str, Any]:
    return {"events": event_log.all()}


async def publish_state() -> Dict[str, Any]:
    engine.ingest_backend(
        history_events=HISTORY_EVENTS,
        resolutions=history_resolutions(),
        actions=[row for row in event_log.all() if row.get("source") == "OPERATOR"],
        alarms=motor_sim.alarms,
        connected=True,
        last_error="",
    )
    motor = motor_sim.as_motor()
    assessment = engine.evaluate(motor, motor_sim.as_telemetry())
    await hub.broadcast({"type": "assessment", "payload": assessment})
    await hub.broadcast({"type": "telemetry", "payload": motor})
    return assessment


def seed_baseline() -> None:
    for _ in range(28):
        motor_sim.step(0.25)
        motor = motor_sim.as_motor()
        engine.analytics.push(motor["sensors"], motor.get("timestamp") or "")


async def sim_loop() -> None:
    while True:
        motor_sim.step(0.25)
        await publish_state()
        await asyncio.sleep(0.25)


@router.post("/demo/scenario")
async def demo_scenario(body: ScenarioIn) -> Dict[str, Any]:
    motor_sim.inject(body.scenario, source="HMI")
    assessment = await publish_state()
    return assessment


@router.post("/demo/reset")
async def demo_reset() -> Dict[str, Any]:
    engine.reset()
    motor_sim.reset()
    seed_baseline()
    assessment = await publish_state()
    return assessment


@router.post("/hmi/start")
async def hmi_start() -> Dict[str, Any]:
    motor_sim.start(source="HMI")
    return await publish_state()


@router.post("/hmi/stop")
async def hmi_stop() -> Dict[str, Any]:
    motor_sim.stop(source="HMI")
    return await publish_state()


@router.post("/hmi/set")
async def hmi_set(body: ParameterIn) -> Dict[str, Any]:
    motor_sim.set_param(body.name, body.value, source="HMI")
    return await publish_state()


@router.post("/recommendation/respond")
async def recommendation_respond(body: RecommendIn) -> Dict[str, Any]:
    rec = respond(body.action, body.message)
    effect = apply_side_effect(body.action.lower())
    if effect == "reduce_load":
        motor_sim.set_param("load", 60.0, source="AERA")
        event_log.emit("OPERATOR_INTERVENTION", source="AERA", context="Load reduced to 60% as accepted alternative.", severity="ATTENTION")
    assessment = await publish_state()
    assessment["recommendation"] = rec
    return assessment


async def ws_aera(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        if engine.latest:
            await ws.send_json({"type": "assessment", "payload": engine.latest})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)
