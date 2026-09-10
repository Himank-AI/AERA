"""In-process Motor 01 simulator. Single source of live machine state."""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from engine.events import event_log
from engine.motor_model import (
    AMBIENT,
    NOMINAL_CURRENT,
    NOMINAL_LOAD,
    NOMINAL_SPEED,
    NOMINAL_TEMP,
    NOMINAL_VIB,
    NOMINAL_VOLTAGE,
    clamp,
    electrical_power_kw,
    frequency_hz,
    torque_nm,
)

PARAM_UNITS = {
    "temperature": "°C",
    "vibration": "mm/s",
    "speed": "RPM",
    "current": "A",
    "voltage": "V",
    "load": "%",
    "power": "kW",
    "rpm": "RPM",
}

# Machine alarms are raw HMI/motor events. AERA interprets them separately.
ALARM_POINTS: Dict[str, Dict[str, Any]] = {
    "temperature": {
        "title": "HIGH TEMPERATURE",
        "unit": "°C",
        "hi": 82.0,
        "hihi": 90.0,
        "deadband": 2.0,
    },
    "vibration": {
        "title": "HIGH VIBRATION",
        "unit": "mm/s",
        "hi": 4.8,
        "hihi": 6.5,
        "deadband": 0.35,
    },
    "current": {
        "title": "HIGH CURRENT",
        "unit": "A",
        "hi": 14.5,
        "hihi": 17.0,
        "deadband": 0.4,
    },
    "voltage": {
        "title": "HIGH VOLTAGE",
        "unit": "V",
        "hi": 248.0,
        "hihi": 260.0,
        "deadband": 3.0,
        "lo": 205.0,
        "lolo": 185.0,
        "title_lo": "LOW VOLTAGE",
    },
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clock(stamp: Optional[str] = None) -> str:
    raw = stamp or _utcnow()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%H:%M:%S")
    except ValueError:
        return raw[11:19] if len(raw) >= 19 else raw


def _lerp(current: float, target: float, rate: float) -> float:
    return current + (target - current) * rate


class MotorSimulator:
    """Deterministic industrial motor with operator-settable live parameters."""

    def __init__(self) -> None:
        self.reset(emit=False)

    def reset(self, emit: bool = True) -> None:
        self.mode = "RUNNING"
        self.health_status = "NORMAL"
        self.direction = "FWD"
        self.fault = False
        self.load_cmd = NOMINAL_LOAD
        self.speed_cmd = NOMINAL_SPEED
        self.overrides: Dict[str, float] = {}
        self.bearing = 0.0
        self.overheat = 0.0
        self.scenario = "NORMAL"
        self.runtime_s = 180.0
        self.start_cycles = 14
        self.energy = 3.4
        self.start_t = 1.0
        self.stop_t = 0.0
        self.active_alarms: Dict[str, Dict[str, Any]] = {}
        self.values = {
            "temperature": NOMINAL_TEMP,
            "vibration": NOMINAL_VIB,
            "speed": NOMINAL_SPEED,
            "current": NOMINAL_CURRENT,
            "voltage": NOMINAL_VOLTAGE,
            "load": NOMINAL_LOAD,
            "power": electrical_power_kw(NOMINAL_VOLTAGE, NOMINAL_CURRENT),
            "torque": 15.5,
            "frequency": frequency_hz(NOMINAL_SPEED),
            "speed_setpoint": NOMINAL_SPEED,
            "energy": 3.4,
            "runtime": 180.0 / 3600.0,
            "start_cycles": 14.0,
        }
        self._last_mode = "RUNNING"
        if emit:
            event_log.emit(
                "MOTOR_STARTED",
                source="SYSTEM",
                context="Simulator reset to healthy running state.",
                severity="NORMAL",
                message="Motor reset to healthy running state",
                condition="Reset",
            )

    def start(self, source: str = "HMI") -> Dict[str, Any]:
        if self.mode in ("RUNNING", "STARTING"):
            return self.snapshot()
        self.fault = False
        self.mode = "STARTING"
        self.start_t = 0.0
        self.start_cycles += 1
        self.values["start_cycles"] = float(self.start_cycles)
        event_log.emit(
            "MOTOR_STARTED",
            source=source,
            context="Operator started Motor 01.",
            severity="NORMAL",
            message="Motor Started",
            condition="Start command",
        )
        return self.snapshot()

    def stop(self, source: str = "HMI") -> Dict[str, Any]:
        if self.mode == "STOPPED":
            return self.snapshot()
        self.mode = "STOPPING"
        self.stop_t = 0.0
        event_log.emit(
            "MOTOR_STOPPED",
            source=source,
            context="Operator stopped Motor 01.",
            severity="NORMAL",
            message="Motor Stopped",
            condition="Stop command",
        )
        return self.snapshot()

    def set_param(self, name: str, value: float, source: str = "HMI") -> Dict[str, Any]:
        key = "speed" if name in ("rpm", "speed") else name
        value = float(value)
        previous = float(self.values.get(key) or 0.0)
        if key == "load":
            value = clamp(value, 0.0, 110.0)
            self.load_cmd = value
            if value >= 80.0 and float(self.overrides.get("temperature") or 0) >= 80.0:
                self.overheat = 0.0
        elif key == "speed":
            value = clamp(value, 0.0, 1800.0)
            self.speed_cmd = value
            self.overrides.pop("speed", None)
        elif key in ("temperature", "vibration", "current", "voltage"):
            limits = {
                "temperature": (20.0, 120.0),
                "vibration": (0.2, 12.0),
                "current": (0.2, 22.0),
                "voltage": (160.0, 280.0),
            }
            lo, hi = limits[key]
            value = clamp(value, lo, hi)
            self.overrides[key] = value
            if key == "vibration":
                if value >= 5.0:
                    self.bearing = clamp((value - NOMINAL_VIB) / 5.3, 0.15, 1.0)
                else:
                    self.bearing = 0.0
            if key == "temperature":
                if value >= 80.0 and self.load_cmd < 80.0:
                    self.overheat = clamp((value - 62.0) / 28.0, 0.15, 1.0)
                elif value < 78.0:
                    self.overheat = 0.0
                elif self.load_cmd >= 80.0:
                    self.overheat = 0.0
        else:
            return self.snapshot()

        event_type = {
            "temperature": "TEMPERATURE_CHANGED",
            "vibration": "VIBRATION_CHANGED",
            "speed": "RPM_CHANGED",
            "current": "CURRENT_CHANGED",
            "voltage": "VOLTAGE_CHANGED",
            "load": "LOAD_CHANGED",
        }.get(key, "PARAMETER_CHANGED")
        severity = "NORMAL"
        if key == "vibration" and value >= 6.0:
            severity = "HIGH"
        elif key == "temperature" and value >= 90.0:
            severity = "HIGH"
        elif key == "temperature" and value >= 82.0:
            severity = "ATTENTION"
        elif key == "load" and value >= 88.0:
            severity = "ATTENTION"
        elif abs(value - previous) >= 2:
            severity = "ATTENTION"
        event_log.emit(
            event_type,
            parameter=key,
            previous=round(previous, 3),
            new=round(value, 3),
            unit=PARAM_UNITS.get(key, ""),
            severity=severity,
            source=source,
            context="{0} set from {1} to {2}".format(key, round(previous, 2), round(value, 2)),
            message="{0} Changed".format(key.replace("_", " ").title()),
            condition="Operator setpoint",
        )
        self._apply_override_immediately(key, value)
        self._sync_alarms()
        return self.snapshot()

    def inject(self, scenario: str, source: str = "HMI") -> Dict[str, Any]:
        scenario = (scenario or "NORMAL").upper()
        self.scenario = scenario
        if scenario in ("NORMAL", "RESET"):
            self.bearing = 0.0
            self.overheat = 0.0
            self.overrides.clear()
            self.scenario = "NORMAL"
            event_log.emit("FAULT_RESOLVED", source=source, context="Fault inject cleared.", severity="NORMAL", message="Fault Cleared")
        elif scenario in ("MOTOR_DEGRADATION", "BEARING", "BEARING_WEAR"):
            self.bearing = 0.72
            self.overheat = 0.18
            self.scenario = "MOTOR_DEGRADATION"
            event_log.emit("FAULT_OCCURRED", source=source, context="Bearing degradation injected.", severity="HIGH", message="Bearing Degradation Injected")
        elif scenario == "MOTOR_OVERHEAT":
            self.overheat = 0.85
            event_log.emit("FAULT_OCCURRED", source=source, context="Overheat condition injected.", severity="HIGH", message="Overheat Injected")
        elif scenario == "VOLTAGE_SPIKE":
            self.overrides["voltage"] = 251.0
            event_log.emit("VOLTAGE_CHANGED", parameter="voltage", previous=self.values["voltage"], new=251.0, unit="V", source=source, severity="ATTENTION", context="Voltage spike injected.")
        elif scenario in ("HIGH_LOAD", "OVERLOAD"):
            self.load_cmd = 92.0
            event_log.emit("LOAD_CHANGED", parameter="load", previous=self.values["load"], new=92.0, unit="%", source=source, severity="ATTENTION", context="High load injected.")
        self._sync_alarms()
        return self.snapshot()

    def _apply_override_immediately(self, key: str, value: float) -> None:
        if key == "load":
            self.values["load"] = value
            if "current" not in self.overrides:
                voltage = float(self.overrides.get("voltage", self.values.get("voltage") or NOMINAL_VOLTAGE))
                voltage_stress = NOMINAL_VOLTAGE / max(voltage, 160.0)
                target_current = NOMINAL_CURRENT * (value / NOMINAL_LOAD) * voltage_stress + 5.1 * self.bearing + 1.5 * self.overheat
                self.values["current"] = _lerp(float(self.values.get("current") or NOMINAL_CURRENT), target_current, 0.7)
                self.values["power"] = electrical_power_kw(voltage, self.values["current"])
            return
        if key == "speed":
            if self.mode in ("RUNNING", "STARTING"):
                self.values["speed"] = value
            return
        self.values[key] = value
        if key == "vibration" and value >= 5.0:
            drag = clamp((value - NOMINAL_VIB) / 5.3, 0.15, 1.0)
            if "current" not in self.overrides:
                self.values["current"] = max(self.values["current"], NOMINAL_CURRENT + 4.9 * drag)
            if "temperature" not in self.overrides:
                self.values["temperature"] = max(self.values["temperature"], NOMINAL_TEMP + 16.0 * drag)
            self.values["speed"] = min(self.values["speed"], NOMINAL_SPEED - 55.0 * drag)
        if key == "vibration" and value < 5.0:
            if "current" not in self.overrides:
                self.values["current"] = min(self.values["current"], NOMINAL_CURRENT + 0.8)
            if "temperature" not in self.overrides:
                self.values["temperature"] = min(self.values["temperature"], NOMINAL_TEMP + 3.0)

    def step(self, dt: float = 0.25) -> Dict[str, Any]:
        t = time.time()
        noise = 0.015 * math.sin(t * 1.7) + 0.01 * math.sin(t * 3.1)

        if self.mode == "STARTING":
            self.start_t = min(1.0, self.start_t + dt / 3.6)
            if self.start_t >= 1.0:
                self.mode = "RUNNING"
        elif self.mode == "STOPPING":
            self.stop_t = min(1.0, self.stop_t + dt / 2.2)
            if self.stop_t >= 1.0:
                self.mode = "STOPPED"

        load = clamp(self.load_cmd, 0.0, 110.0)
        setpoint = self.speed_cmd
        if "speed" in self.overrides:
            setpoint = self.overrides["speed"]

        if self.mode == "STOPPED":
            target_speed = 0.0
            target_current = 0.32
            target_vib = 0.35
            target_temp = AMBIENT + 6.0
            inrush = 0.0
        elif self.mode == "STOPPING":
            target_speed = max(0.0, self.values["speed"] * (1.0 - self.stop_t))
            target_current = 0.4
            target_vib = 0.6
            target_temp = AMBIENT + 10.0
            inrush = 0.0
        elif self.mode == "STARTING":
            inrush = 4.2 * (1.0 - self.start_t)
            target_speed = setpoint * self.start_t
            target_current = NOMINAL_CURRENT * (load / NOMINAL_LOAD) + inrush
            target_vib = NOMINAL_VIB + 1.4 * (1.0 - self.start_t)
            target_temp = NOMINAL_TEMP - 4.0 + 6.0 * self.start_t
        else:
            inrush = 0.0
            droop = 0.35 * max(0.0, load - NOMINAL_LOAD) + 70.0 * self.bearing + 22.0 * self.overheat
            target_speed = max(0.0, setpoint - droop)
            voltage_stress = NOMINAL_VOLTAGE / max(float(self.overrides.get("voltage", self.values["voltage"])), 160.0)
            target_current = NOMINAL_CURRENT * (load / NOMINAL_LOAD) * voltage_stress + 5.1 * self.bearing + 1.5 * self.overheat
            target_vib = NOMINAL_VIB + 0.014 * max(0.0, load - 20.0) + 5.4 * self.bearing + 0.5 * self.overheat
            target_vib += max(0.0, target_speed / NOMINAL_SPEED - 1.0) * 1.3
            target_temp = 48.0 + 0.22 * load + 22.0 * self.bearing + 16.0 * self.overheat

        voltage_target = float(self.overrides["voltage"]) if "voltage" in self.overrides else NOMINAL_VOLTAGE + 0.6 * noise
        if "vibration" in self.overrides:
            target_vib = float(self.overrides["vibration"])
        if "temperature" in self.overrides:
            target_temp = float(self.overrides["temperature"])
        if "current" in self.overrides:
            target_current = float(self.overrides["current"])

        speed_rate = 0.55 if self.mode in ("STARTING", "STOPPING") else 0.42
        self.values["speed"] = _lerp(self.values["speed"], target_speed, speed_rate)
        if "current" in self.overrides:
            self.values["current"] = float(self.overrides["current"])
        else:
            self.values["current"] = _lerp(self.values["current"], target_current, 0.42)
        if "vibration" in self.overrides:
            self.values["vibration"] = float(self.overrides["vibration"])
        else:
            self.values["vibration"] = _lerp(self.values["vibration"], target_vib, 0.38)
        if "temperature" in self.overrides:
            self.values["temperature"] = float(self.overrides["temperature"])
        else:
            self.values["temperature"] = _lerp(self.values["temperature"], target_temp, 0.12 if self.mode == "RUNNING" else 0.08)
        if "voltage" in self.overrides:
            self.values["voltage"] = float(self.overrides["voltage"])
        else:
            self.values["voltage"] = _lerp(self.values["voltage"], voltage_target, 0.5)
        self.values["load"] = load

        if self.mode == "RUNNING":
            if "speed" not in self.overrides:
                self.values["speed"] += 1.1 * noise
            if "vibration" not in self.overrides:
                self.values["vibration"] += 0.03 * noise
            if "current" not in self.overrides:
                self.values["current"] += 0.04 * noise
            if "temperature" not in self.overrides:
                self.values["temperature"] += 0.05 * noise

        voltage = clamp(self.values["voltage"], 160.0, 280.0)
        current = clamp(self.values["current"], 0.2, 22.0)
        speed = max(0.0, self.values["speed"])
        power = electrical_power_kw(voltage, current)
        self.values["voltage"] = voltage
        self.values["current"] = current
        self.values["speed"] = speed
        self.values["power"] = power
        self.values["torque"] = torque_nm(power, speed) if speed > 1 else 0.0
        self.values["frequency"] = frequency_hz(speed)
        self.values["speed_setpoint"] = setpoint
        if self.mode in ("RUNNING", "STARTING"):
            self.runtime_s += dt
            self.energy += power * dt / 3600.0
        self.values["runtime"] = self.runtime_s / 3600.0
        self.values["energy"] = self.energy
        self.values["start_cycles"] = float(self.start_cycles)

        self._sync_alarms()
        if self.mode != self._last_mode:
            self._last_mode = self.mode
        return self.snapshot()

    def _alarm_level(self, key: str, value: float, existing: Optional[Dict[str, Any]]) -> Optional[Tuple[str, str, str]]:
        spec = ALARM_POINTS[key]
        dead = float(spec["deadband"])
        if key == "voltage":
            hihi, hi, lo, lolo = spec["hihi"], spec["hi"], spec["lolo"], spec["lo"]
            # lolo is more severe low; lo is high-low. Naming: lolo=185, lo=205.
            if value >= hihi or (existing and existing.get("level") == "HIHI" and existing.get("side") == "high" and value >= hihi - dead):
                return "HIHI", "Above High-High threshold", spec["title"]
            if value <= spec["lolo"] or (existing and existing.get("level") == "HIHI" and existing.get("side") == "low" and value <= spec["lolo"] + dead):
                return "HIHI", "Below Low-Low threshold", spec["title_lo"]
            if value >= hi or (existing and existing.get("level") == "HI" and existing.get("side") == "high" and value >= hi - dead):
                return "HI", "Above High threshold", spec["title"]
            if value <= spec["lo"] or (existing and existing.get("level") == "HI" and existing.get("side") == "low" and value <= spec["lo"] + dead):
                return "HI", "Below Low threshold", spec["title_lo"]
            return None
        hihi, hi = spec["hihi"], spec["hi"]
        if value >= hihi or (existing and existing.get("level") == "HIHI" and value >= hihi - dead):
            return "HIHI", "Above High-High threshold", spec["title"]
        if value >= hi or (existing and existing.get("level") == "HI" and value >= hi - dead):
            return "HI", "Above High threshold", spec["title"]
        return None

    def _sync_alarms(self) -> None:
        now = _utcnow()
        desired: Dict[str, Dict[str, Any]] = {}
        for key, spec in ALARM_POINTS.items():
            value = float(self.values.get(key) or 0.0)
            existing = self.active_alarms.get(key)
            ranked = self._alarm_level(key, value, existing)
            if not ranked:
                continue
            level, condition, title = ranked
            side = "low" if "Low" in condition else "high"
            stamp = (existing or {}).get("timestamp") or now
            desired[key] = {
                "id": "{0}_{1}".format(key.upper(), level),
                "title": title,
                "name": title,
                "asset": "MOTOR-01",
                "equipment": "MOTOR-01",
                "parameter": key,
                "value": round(value, 3),
                "unit": spec["unit"],
                "condition": condition,
                "level": level,
                "side": side,
                "priority": "HIGH" if level == "HIHI" else "MEDIUM",
                "status": "ACTIVE",
                "alarm_status": "Active",
                "timestamp": stamp,
                "clock": _clock(stamp),
                "interrupt_operator": level == "HIHI",
            }

        for key, alarm in list(self.active_alarms.items()):
            if key in desired:
                nxt = desired[key]
                if nxt["level"] != alarm.get("level") or nxt["title"] != alarm.get("title"):
                    event_log.emit(
                        "ALARM_TRIGGERED",
                        parameter=nxt["parameter"],
                        new=nxt["value"],
                        unit=nxt["unit"],
                        severity="HIGH" if nxt["level"] == "HIHI" else "ATTENTION",
                        source="MOTOR",
                        context=nxt["title"],
                        message=nxt["title"].title(),
                        alarm_status="Active",
                        condition=nxt["condition"],
                    )
                else:
                    nxt["timestamp"] = alarm.get("timestamp") or nxt["timestamp"]
                    nxt["clock"] = _clock(nxt["timestamp"])
                continue
            event_log.emit(
                "ALARM_RETURNED",
                parameter=alarm.get("parameter") or key,
                previous=alarm.get("value"),
                new=round(float(self.values.get(key) or 0.0), 3),
                unit=alarm.get("unit") or PARAM_UNITS.get(key, ""),
                severity="NORMAL",
                source="MOTOR",
                context=alarm.get("title") or key,
                message="{0} Return".format(alarm.get("title") or key),
                alarm_status="Return",
                condition="Returned to normal band",
                outcome="Alarm returned",
            )

        for key, alarm in desired.items():
            if key not in self.active_alarms:
                event_log.emit(
                    "ALARM_TRIGGERED",
                    parameter=alarm["parameter"],
                    new=alarm["value"],
                    unit=alarm["unit"],
                    severity="HIGH" if alarm["level"] == "HIHI" else "ATTENTION",
                    source="MOTOR",
                    context=alarm["title"],
                    message=alarm["title"].title(),
                    alarm_status="Active",
                    condition=alarm["condition"],
                )

        self.active_alarms = desired
        hihi = any(row.get("level") == "HIHI" for row in desired.values())
        hi = bool(desired)
        if hihi:
            self.health_status = "ALARM"
            self.fault = True
        elif hi:
            self.health_status = "ANOMALY"
            self.fault = False
        else:
            self.health_status = "NORMAL"
            self.fault = False

    def as_motor(self) -> Dict[str, Any]:
        sensors = {key: round(float(value), 3) for key, value in self.values.items()}
        drive = "RUN" if self.mode in ("RUNNING", "STARTING") else "STOP"
        return {
            "code": "MOTOR-01",
            "name": "Motor 01",
            "asset_type": "motor",
            "operating_mode": self.mode,
            "status": self.health_status,
            "direction": self.direction,
            "drive_status": drive,
            "fault_state": self.fault,
            "sensors": sensors,
            "timestamp": _utcnow(),
            "scenario": self.scenario,
            "running": self.mode in ("RUNNING", "STARTING"),
            "source": "shared-runtime",
        }

    def as_telemetry(self) -> Dict[str, Any]:
        motor = self.as_motor()
        return {
            "timestamp": motor["timestamp"],
            "scenario": self.scenario,
            "running": motor["running"],
            "mode": self.mode,
            "assets": {"MOTOR-01": motor},
        }

    def snapshot(self) -> Dict[str, Any]:
        return self.as_telemetry()

    @property
    def alarms(self) -> List[Dict[str, Any]]:
        rows = [dict(row) for row in self.active_alarms.values()]
        rows.sort(key=lambda row: (0 if row.get("level") == "HIHI" else 1, str(row.get("parameter") or "")))
        return rows


motor_sim = MotorSimulator()
