"""Read-only client for the Motor + HMI backend. AERA never invents live values."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx
import websockets

from config import settings

OnTelemetry = Callable[[Dict[str, Any]], Awaitable[None]]


class MotorBackendClient:
    def __init__(self) -> None:
        self.api = settings.motor_api_url.rstrip("/")
        self.ws_url = settings.motor_ws_url
        self.motor_code = settings.motor_code
        self.connected = False
        self.last_error = ""
        self.latest_telemetry: Dict[str, Any] = {}
        self.history_events: List[Dict[str, Any]] = []
        self.incidents: List[Dict[str, Any]] = []
        self.alarms: List[Dict[str, Any]] = []
        self.actions: List[Dict[str, Any]] = []
        self.resolutions: List[Dict[str, Any]] = []
        self.sops: List[Dict[str, Any]] = []
        self.machines: List[Dict[str, Any]] = []
        self.machine_id: Optional[int] = None
        self._on_telemetry: Optional[OnTelemetry] = None
        self._stop = asyncio.Event()

    def attach(self, on_telemetry: OnTelemetry) -> None:
        self._on_telemetry = on_telemetry

    async def get(self, path: str, default: Any = None) -> Any:
        url = "{0}{1}".format(self.api, path)
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            self.last_error = str(exc)
            return default

    async def post(self, path: str, body: Dict[str, Any]) -> Any:
        url = "{0}{1}".format(self.api, path)
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            return response.json()

    async def refresh_history(self) -> None:
        events = await self.get("/api/history/events?machine={0}".format(self.motor_code), [])
        if not events:
            hist = await self.get("/api/machines/1/history", {})
            events = (hist or {}).get("historical_events") or []
        self.history_events = events if isinstance(events, list) else []
        self.incidents = await self.get("/api/incidents", []) or []
        self.alarms = await self.get("/api/alarms/active", []) or []
        actions = await self.get("/api/operator/actions", None)
        if actions is None:
            timeline = await self.get("/api/timeline", [])
            actions = [row for row in (timeline or []) if row.get("kind") == "action"]
        self.actions = actions or []
        self.resolutions = await self.get("/api/resolutions", []) or []
        sops = await self.get("/api/sops", None)
        if sops is None:
            sops = await self.get("/api/sop", [])
        self.sops = sops or []
        machines = await self.get("/api/machines", []) or []
        self.machines = machines
        for row in machines:
            if row.get("code") == self.motor_code:
                self.machine_id = row.get("id")
                break

    def extract_motor(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        assets = (telemetry or {}).get("assets") or {}
        motor = assets.get(self.motor_code) or {}
        sensors = dict(motor.get("sensors") or {})
        speed = float(sensors.get("speed") or 0.0)
        power = float(sensors.get("power") or 0.0)
        if "frequency" not in sensors and speed:
            sensors["frequency"] = round(speed / 30.0, 2)
        if "torque" not in sensors and speed:
            sensors["torque"] = round((power * 9550.0) / max(speed, 1.0), 2)
        if "speed_setpoint" not in sensors:
            sensors["speed_setpoint"] = 1450.0
        return {
            "code": motor.get("code") or self.motor_code,
            "name": motor.get("name") or "Motor 01",
            "asset_type": motor.get("asset_type") or "motor",
            "operating_mode": motor.get("operating_mode") or telemetry.get("mode") or "UNKNOWN",
            "status": motor.get("status") or "UNKNOWN",
            "direction": motor.get("direction") or "FWD",
            "drive_status": motor.get("drive_status") or motor.get("operating_mode") or "UNKNOWN",
            "fault_state": bool(motor.get("fault_state")),
            "sensors": sensors,
            "timestamp": telemetry.get("timestamp"),
            "scenario": telemetry.get("scenario"),
            "running": bool(telemetry.get("running")),
            "source": "motor-hmi-backend",
        }

    async def loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.refresh_history()
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
                    self.connected = True
                    self.last_error = ""
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        try:
                            message = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        kind = message.get("type")
                        payload = message.get("payload") or {}
                        if kind in ("telemetry", "scenario"):
                            self.latest_telemetry = payload
                            if self._on_telemetry:
                                await self._on_telemetry(payload)
                        elif kind == "alarm":
                            self.alarms = await self.get("/api/alarms/active", self.alarms) or self.alarms
            except Exception as exc:
                self.connected = False
                self.last_error = str(exc)
                await asyncio.sleep(2.0)

    def stop(self) -> None:
        self._stop.set()


motor_client = MotorBackendClient()
