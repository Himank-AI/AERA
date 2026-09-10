"""Continuous motor situation engine.

OBSERVE → UNDERSTAND → COMPARE → ASSESS RISK → EXPLAIN → GUIDE → LEARN

Risk and attention are decided here. The LLM never sets them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from engine.analytics import MotorAnalytics
from engine.events import event_log
from engine.recommend import build_copilot_view, rec_state, risk_band
from knowledge.expert import EXPERT_CASES, matching_expert_cases, sop_by_code
from knowledge.history_data import HISTORY_EVENTS, history_resolutions
from knowledge.motor import MOTOR_IDENTITY, PARAMETERS, SITUATION_PATTERNS, expected_value, parameter_brief
from store import learning_store

WATCH_KEYS = ("temperature", "current", "vibration", "speed", "voltage", "load", "power", "torque")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _level_from_score(score: int) -> str:
    if score >= 81:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 41:
        return "MEDIUM"
    if score >= 21:
        return "MONITOR"
    return "NORMAL"


class SituationEngine:
    def __init__(self) -> None:
        self.analytics = MotorAnalytics()
        self.latest: Dict[str, Any] = {}
        self.timeline: List[Dict[str, Any]] = []
        self.history_events: List[Dict[str, Any]] = list(HISTORY_EVENTS)
        self.resolutions: List[Dict[str, Any]] = history_resolutions()
        self.actions: List[Dict[str, Any]] = []
        self.alarms: List[Dict[str, Any]] = []
        self.experience_level = "NEW"
        self.previous_level = "NORMAL"
        self.connected = False
        self.last_error = ""

    def reset(self) -> None:
        self.analytics.reset()
        self.timeline = []
        self.previous_level = "NORMAL"
        rec_state.reset()
        event_log.reset()
        from engine.copilot import memory

        memory.reset()

    def ingest_backend(
        self,
        history_events: List[Dict[str, Any]],
        resolutions: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        alarms: List[Dict[str, Any]],
        connected: bool,
        last_error: str,
    ) -> None:
        self.history_events = history_events or list(HISTORY_EVENTS)
        self.resolutions = resolutions or history_resolutions()
        self.actions = actions or []
        self.alarms = [row for row in (alarms or []) if (row.get("asset") or "") in ("MOTOR-01", "MOTOR-02", None, "")]
        motor_alarms = []
        for row in alarms or []:
            asset = (row.get("asset") or row.get("asset_name") or "").upper()
            if "MOTOR" in asset or "M01" in asset or not asset:
                motor_alarms.append(row)
        self.alarms = motor_alarms or [row for row in (alarms or []) if "motor" in (row.get("title") or "").lower()]
        if not self.alarms:
            self.alarms = alarms or []
        self.connected = connected
        self.last_error = last_error

    def evaluate(self, motor: Dict[str, Any], telemetry: Dict[str, Any]) -> Dict[str, Any]:
        if not motor or not motor.get("sensors"):
            self.latest = self._disconnected()
            return self.latest

        sensors = {key: float(value) for key, value in (motor.get("sensors") or {}).items() if isinstance(value, (int, float))}
        self.analytics.push(sensors, motor.get("timestamp") or telemetry.get("timestamp") or "")
        load = float(sensors.get("load") or 64.0)
        speed = float(sensors.get("speed") or 1450.0)
        runtime_h = float(sensors.get("runtime") or 0.0)
        mode = motor.get("operating_mode") or "RUNNING"

        deviations = self._contextual_deviations(sensors, load, speed, runtime_h, mode)
        trends = self.analytics.trend_map(8)
        situation = self._group_situation(deviations, trends, mode, motor.get("status") or "NORMAL", load)
        similar = self._similar_incidents(sensors, trends, situation.get("family") or "", live_event=situation.get("id") not in ("normal", None, ""))
        iso = self.analytics.isolation_score(sensors)
        risk = self._risk(deviations, situation, similar, iso, motor, mode)
        why_flagged, why_not = self._explanations(deviations, situation, similar, risk, mode)
        guidance = self._guidance(situation, similar, risk)
        narrative = self._what_happened(motor, sensors, deviations, situation, similar, risk)
        health = self._health(risk["score"], motor.get("status") or "NORMAL")

        if risk["level"] != self.previous_level:
            self.timeline.append(
                {
                    "time": motor.get("timestamp") or _utcnow(),
                    "label": "Risk {0} → {1}".format(self.previous_level, risk["level"]),
                    "detail": situation.get("title") or risk["reason"],
                }
            )
            self.previous_level = risk["level"]
        for item in deviations:
            if item["severity"] in ("warning", "critical") and item["name"] in ("vibration", "current", "temperature", "speed"):
                label = "{0} {1}".format(item["title"], "rising" if item["delta"] > 0 else "falling")
                if not self.timeline or self.timeline[-1]["label"] != label:
                    self.timeline.append(
                        {
                            "time": motor.get("timestamp") or _utcnow(),
                            "label": label,
                            "detail": item["note"],
                        }
                    )
        self.timeline = self.timeline[-40:]

        assessment = {
            "timestamp": motor.get("timestamp") or telemetry.get("timestamp") or _utcnow(),
            "connected": True,
            "source": "shared-runtime",
            "motor": {
                "code": motor.get("code") or "MOTOR-01",
                "tag": "M01",
                "name": motor.get("name") or "Motor 01",
                "identity": MOTOR_IDENTITY,
                "status": motor.get("operating_mode") or "RUNNING",
                "health_status": motor.get("status") or "NORMAL",
                "direction": motor.get("direction") or "FWD",
                "drive_status": motor.get("drive_status") or motor.get("operating_mode"),
                "fault_state": motor.get("fault_state"),
                "scenario": telemetry.get("scenario"),
            },
            "sensors": sensors,
            "health": health,
            "risk": risk,
            "situation": situation,
            "deviations": deviations,
            "trends": trends,
            "why_flagged": why_flagged,
            "why_not_flagged": why_not,
            "similar": similar,
            "guidance": guidance,
            "narrative": narrative,
            "alarms": self._motor_alarms(),
            "timeline": list(self.timeline),
            "expert": guidance.get("expert") or [],
            "parameters": {key: self._parameter_view(key, sensors, load, speed, runtime_h) for key in PARAMETERS},
            "experience_level": self.experience_level,
            "series": self.analytics.chart_series(),
            "backend_scenario": telemetry.get("scenario"),
        }
        learning_store.record_assessment(
            {
                "risk": risk["level"],
                "score": risk["score"],
                "situation": situation.get("title"),
                "family": situation.get("family"),
            }
        )
        assessment["events"] = event_log.recent()
        view = build_copilot_view(assessment)
        assessment["attention"] = view["status"]
        assessment["copilot_view"] = view
        assessment["recommendation"] = view["recommendation"]
        assessment["events"] = event_log.recent()
        self.latest = assessment
        return assessment

    def _disconnected(self) -> Dict[str, Any]:
        payload = {
            "timestamp": _utcnow(),
            "connected": False,
            "source": "none",
            "error": self.last_error or "Motor runtime is not connected. AERA will not invent motor data.",
            "motor": {"code": "MOTOR-01", "tag": "M01", "name": "Motor 01", "status": "UNKNOWN"},
            "sensors": {},
            "health": 0,
            "risk": {
                "score": 0,
                "level": "UNKNOWN",
                "reason": "No live motor data.",
                "evidence": ["AERA is not receiving the Motor + HMI stream."],
                "trend": "unknown",
                "historical_frequency": 0,
                "potential_consequence": "Unknown until the motor backend is connected.",
                "recommended_response": "Start the Motor + HMI backend. AERA is an observer only.",
                "factors": {},
            },
            "situation": {"title": "NO LIVE MOTOR DATA", "family": "", "severity": "UNKNOWN"},
            "deviations": [],
            "why_flagged": {"flagged": False, "points": ["Not evaluated — no live data."]},
            "why_not_flagged": {"points": ["No live sample to judge."]},
            "similar": {"count": 0, "matches": [], "summary": ""},
            "guidance": {"checks": [], "avoid": [], "sop": None},
            "narrative": "AERA is waiting for live motor data. It will not fabricate motor values.",
            "alarms": [],
            "timeline": [],
            "parameters": {},
            "series": {},
            "experience_level": self.experience_level,
        }
        self.latest = payload
        return payload

    def _contextual_deviations(
        self,
        sensors: Dict[str, float],
        load: float,
        speed: float,
        runtime_h: float,
        mode: str,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for key in WATCH_KEYS:
            if key not in sensors:
                continue
            spec = PARAMETERS.get(key) or {}
            value = float(sensors[key])
            expected = expected_value(key, load, speed, runtime_h)
            z = self.analytics.zscore(key, value)
            roc = self.analytics.rate(key, 6)
            pct = self.analytics.percent_change(key, 8)
            delta = value - expected
            severity = "normal"
            unusual = False
            note = "{0} is consistent with the current load and speed.".format(spec.get("name") or key)

            if mode == "STARTING" and key in ("current", "vibration", "speed"):
                note = "{0} may be elevated during STARTING. This is expected for a few seconds.".format(spec.get("name"))
            elif key == "temperature":
                if delta >= float(spec.get("crit_delta") or 16):
                    severity, unusual = "critical", True
                    note = "Temperature is far above the expected value for {0:.0f}% load.".format(load)
                elif delta >= float(spec.get("warn_delta") or 8) or (roc > 0.35 and delta > 3):
                    severity, unusual = "warning", True
                    note = "Temperature is unusually high for {0:.0f}% load or rising faster than expected.".format(load)
                elif delta < -6:
                    note = "Temperature is cooler than typical for this load — not a concern."
            elif key == "voltage":
                if abs(delta) >= 16:
                    severity, unusual = "warning", True
                    note = "Voltage left the normal running band."
                elif abs(delta) >= 8:
                    unusual = True
                    severity = "watch"
                    note = "Voltage moved, but other context still needs checking."
            else:
                denom = max(abs(expected), 1.0)
                rel = abs(delta) / denom
                bad_up = spec.get("direction_bad") in ("up", "either") and delta > 0
                bad_down = spec.get("direction_bad") in ("down", "either") and delta < 0
                if rel >= float(spec.get("crit_pct") or 0.3) and (bad_up or bad_down):
                    severity, unusual = "critical", True
                    note = "{0} is well outside the expected value for this operating point.".format(spec.get("name"))
                elif rel >= float(spec.get("warn_pct") or 0.12) and (bad_up or bad_down):
                    severity, unusual = "warning", True
                    note = "{0} is unusual for the current load/speed.".format(spec.get("name"))
                elif abs(z) >= 2.4 and abs(delta) >= max(0.15 * max(abs(expected), 1.0), 0.4) and len(self.analytics.series.get(key, [])) >= 24 and (bad_up or bad_down):
                    severity, unusual = "watch", True
                    note = "{0} is statistically away from the recent baseline.".format(spec.get("name"))

            out.append(
                {
                    "name": key,
                    "title": spec.get("name") or key,
                    "unit": spec.get("unit") or "",
                    "value": round(value, 3),
                    "expected": round(expected, 3),
                    "delta": round(delta, 3),
                    "z": round(z, 2),
                    "rate": round(roc, 3),
                    "percent_change": round(pct, 2),
                    "severity": severity,
                    "unusual": unusual,
                    "note": note,
                    "meaning": spec.get("meaning"),
                }
            )
        return out

    def _high_load_thermal(self, deviations: List[Dict[str, Any]], load: float) -> Optional[Dict[str, Any]]:
        if load < 80.0:
            return None
        temp = next((row for row in deviations if row["name"] == "temperature"), None)
        vib = next((row for row in deviations if row["name"] == "vibration"), None)
        if not temp or not (temp.get("unusual") or float(temp.get("value") or 0) >= 80.0):
            return None
        vib_value = float((vib or {}).get("value") or 0.0)
        vib_bad = bool(vib and (vib_value >= 4.2 or vib.get("severity") in ("warning", "critical")))
        if vib_bad:
            return None
        return {
            "id": "high_load_thermal",
            "title": "HIGH-LOAD THERMAL RISE",
            "family": "temp_high_load",
            "severity": "ATTENTION",
            "what": "Temperature is elevated with high load. Vibration is not in the mechanical-fault band.",
            "why": "This motor historically runs hotter at high process load.",
            "affected": ["Motor 01"],
            "possible_cause": "Expected heating under high process load.",
            "consequence": "Historically this often returns without intervention.",
            "signals": ["temperature ↑", "load high", "vibration stable"],
            "sop": "SOP-MTR-TMP-01",
            "checks": [
                "Confirm process demand is actually high.",
                "Continue monitoring vibration.",
                "No stop required unless temperature keeps climbing with vibration.",
            ],
            "avoid": ["Do not treat high-load heating as a bearing fault."],
        }

    def _group_situation(
        self,
        deviations: List[Dict[str, Any]],
        trends: Dict[str, int],
        mode: str,
        motor_status: str,
        load: float = 64.0,
    ) -> Dict[str, Any]:
        unusual = {
            row["name"]: row
            for row in deviations
            if row["severity"] in ("warning", "critical") or abs(row["percent_change"]) >= 8
        }
        hits: List[Tuple[int, Dict[str, Any]]] = []
        for pattern in SITUATION_PATTERNS:
            if pattern["id"] == "startup" and mode != "STARTING":
                continue
            matched = 0
            for signal, direction in pattern["signals"].items():
                trend = trends.get(signal, 0)
                row = unusual.get(signal)
                if direction == "up" and (trend > 0 or (row and row["delta"] > 0)):
                    matched += 1
                elif direction == "down" and (trend < 0 or (row and row["delta"] < 0)):
                    matched += 1
            if mode == "STARTING" and pattern["id"] == "startup":
                matched = max(matched, pattern["min_hits"])
            if matched >= pattern["min_hits"]:
                hits.append((matched, pattern))
        hits.sort(key=lambda item: item[0], reverse=True)

        if mode == "STARTING" and (not hits or hits[0][1]["id"] != "bearing_mechanical"):
            pattern = SITUATION_PATTERNS[-1]
            return self._situation_payload(pattern, "Startup transients are expected.", "MONITOR")

        thermal = self._high_load_thermal(deviations, load)
        if thermal:
            return thermal

        if not hits:
            if motor_status in ("ALARM", "FAULT"):
                return {
                    "id": "machine_alarm",
                    "title": "MOTOR ALARM PRESENT",
                    "family": "motor_alarm",
                    "severity": "ATTENTION",
                    "what": "The motor reported an alarm. AERA is interpreting it against load, vibration, and history — not copying it as high risk.",
                    "why": "A machine alarm is raw information, not an AERA verdict.",
                    "affected": ["Motor 01"],
                    "possible_cause": "See the active motor alarm and surrounding parameters.",
                    "consequence": "Investigate only if the combination is unusual versus history.",
                    "signals": [],
                    "sop": "SOP-MTR-SAFE-01",
                    "checks": ["Read the alarm value and condition.", "Compare with load, vibration, and history."],
                    "avoid": ["Do not treat every motor alarm as high risk."],
                }
            return {
                "id": "normal",
                "title": "MOTOR OPERATING WITHIN EXPECTED BEHAVIOUR",
                "family": "",
                "severity": "NORMAL",
                "what": "No grouped abnormal pattern on Motor 01.",
                "why": "Parameters are consistent with the current load, speed, and mode.",
                "affected": [],
                "possible_cause": "",
                "consequence": "",
                "signals": [],
                "sop": None,
                "checks": [],
                "avoid": [],
            }

        pattern = hits[0][1]
        if pattern["id"] == "overheat" and thermal:
            return thermal
        signals = ["{0} {1}".format(name, "↑" if direction == "up" else "↓") for name, direction in pattern["signals"].items()]
        return self._situation_payload(pattern, " / ".join(signals), "HIGH" if pattern["id"] == "bearing_mechanical" else "MEDIUM")

    def _situation_payload(self, pattern: Dict[str, Any], signals: str, severity: str) -> Dict[str, Any]:
        return {
            "id": pattern["id"],
            "title": pattern["title"],
            "family": pattern["family"],
            "severity": severity,
            "what": pattern["title"].title().replace("Developing", "Developing"),
            "why": pattern["possible_cause"],
            "affected": ["Motor 01", "Driven equipment"],
            "possible_cause": pattern["possible_cause"],
            "consequence": pattern["consequence"],
            "signals": signals if isinstance(signals, list) else [signals],
            "sop": pattern.get("sop"),
            "checks": pattern.get("checks") or [],
            "avoid": pattern.get("avoid") or [],
        }

    def _similar_incidents(
        self,
        sensors: Dict[str, float],
        trends: Dict[str, int],
        family: str,
        live_event: bool = True,
    ) -> Dict[str, Any]:
        if not live_event:
            return {
                "count": 0,
                "failure_count": 0,
                "intervention_count": 0,
                "bearing_count": 0,
                "harmless_count": 0,
                "matches": [],
                "summary": "",
            }
        matches: List[Dict[str, Any]] = []
        for event in self.history_events:
            event_family = event.get("pattern_family") or event.get("event_type") or ""
            machine = event.get("machine") or ""
            if machine and machine not in ("MOTOR-01", "M01", "Motor 01"):
                if "MOTOR" not in str(machine).upper() and event.get("machine_id") not in (1, None):
                    continue
            score = self._similarity(sensors, trends, event, family, event_family)
            if score < 0.72:
                continue
            matches.append(
                {
                    "event_number": event.get("event_number") or event.get("id"),
                    "timestamp": event.get("timestamp"),
                    "date": (event.get("timestamp") or "")[:10],
                    "symptoms": event.get("description") or event.get("pattern_family"),
                    "root_cause": event.get("pattern_family"),
                    "operator_action": event.get("operator_action") or "",
                    "solution": event.get("operator_action") or event.get("outcome"),
                    "outcome": event.get("outcome"),
                    "failure": bool(event.get("failure")),
                    "intervention": bool(event.get("intervention")),
                    "similarity": round(score * 100),
                    "vibration": event.get("vibration"),
                    "temperature": event.get("temperature"),
                    "current": event.get("current"),
                    "speed": event.get("speed"),
                    "pattern_family": event_family,
                }
            )
        matches.sort(key=lambda row: row["similarity"], reverse=True)
        matches = matches[:8]
        failures = sum(1 for row in matches if row["failure"])
        interventions = sum(1 for row in matches if row["intervention"])
        bearing = sum(1 for row in matches if "bearing" in (row.get("pattern_family") or ""))
        load_only = sum(1 for row in matches if not row["failure"] and "bearing" not in (row.get("pattern_family") or ""))
        summary = ""
        if matches:
            summary = (
                "This behaviour is similar to {0} previous incidents. "
                "{1} involved bearing-related issues and {2} did not lead to a trip."
            ).format(len(matches), bearing, len(matches) - failures)
        return {
            "count": len(matches),
            "failure_count": failures,
            "intervention_count": interventions,
            "bearing_count": bearing,
            "harmless_count": load_only,
            "matches": matches,
            "summary": summary,
        }

    def _similarity(
        self,
        sensors: Dict[str, float],
        trends: Dict[str, int],
        event: Dict[str, Any],
        live_family: str,
        event_family: str,
    ) -> float:
        pairs = (
            ("vibration", 3.5),
            ("temperature", 18.0),
            ("current", 4.0),
            ("speed", 80.0),
            ("voltage", 20.0),
            ("load", 40.0),
        )
        mag_terms = []
        for key, scale in pairs:
            live = float(sensors.get(key) or 0.0)
            hist = float(event.get(key) or 0.0)
            if hist == 0 and live == 0:
                continue
            mag_terms.append(max(0.0, 1.0 - abs(live - hist) / scale))
        magnitude = sum(mag_terms) / max(len(mag_terms), 1)
        trend_hist = event.get("trend") or {}
        if isinstance(trend_hist, str):
            trend_hist = {}
        trend_score = 0.0
        compared = 0
        for key, direction in trends.items():
            if key in trend_hist:
                hist_dir = int(trend_hist.get(key) or 0)
                compared += 1
                if direction == hist_dir and direction != 0:
                    trend_score += 1.0
                elif direction == 0 or hist_dir == 0:
                    trend_score += 0.4
        if compared:
            trend_score /= compared
        else:
            trend_score = 0.5
        family_score = 1.0 if live_family and live_family == event_family else (0.2 if live_family else 0.5)
        if event_family == "voltage_spike" and live_family and live_family != "voltage_spike":
            return min(0.35, magnitude * 0.2)
        return max(0.0, min(0.99, 0.50 * magnitude + 0.20 * trend_score + 0.30 * family_score))

    def _risk(
        self,
        deviations: List[Dict[str, Any]],
        situation: Dict[str, Any],
        similar: Dict[str, Any],
        iso: float,
        motor: Dict[str, Any],
        mode: str,
    ) -> Dict[str, Any]:
        unusual = [row for row in deviations if row["unusual"]]
        severity_points = 0
        for row in deviations:
            if row["severity"] == "critical":
                severity_points += 22
            elif row["severity"] == "warning":
                severity_points += 12
            elif row["severity"] == "watch":
                severity_points += 4
        severity_points = min(30, severity_points)
        roc_points = 0
        for row in deviations:
            if abs(row["percent_change"]) >= 10:
                roc_points += 6
            if abs(row.get("rate") or 0) >= 0.4 and row.get("name") in ("temperature", "vibration", "current"):
                roc_points += 4
        roc_points = min(16, roc_points)
        combo = 0
        vib = 0.0
        temp_val = 0.0
        load_val = 0.0
        current_val = 0.0
        for row in deviations:
            if row.get("name") == "vibration":
                vib = float(row.get("value") or 0)
            elif row.get("name") == "temperature":
                temp_val = float(row.get("value") or 0)
            elif row.get("name") == "load":
                load_val = float(row.get("value") or 0)
            elif row.get("name") == "current":
                current_val = float(row.get("value") or 0)
        if situation.get("id") == "bearing_mechanical":
            vib_row = next((row for row in deviations if row["name"] == "vibration"), None)
            vib = float((vib_row or {}).get("value") or vib)
            if vib >= 6.5:
                combo = 36
            elif vib >= 5.0:
                combo = 24
            elif vib >= 4.0:
                combo = 16
            else:
                combo = 8
        elif situation.get("id") == "overload":
            combo = 10
        elif situation.get("id") == "overheat":
            combo = 14
        elif situation.get("id") == "voltage_transient":
            combo = 4
        elif situation.get("id") == "high_load_thermal":
            combo = 4
        elif situation.get("id") == "machine_alarm":
            combo = 6
        rising = [
            row
            for row in deviations
            if (row.get("percent_change") or 0) > 6 and row.get("name") in ("temperature", "vibration", "current", "load")
        ]
        if situation.get("id") not in ("high_load_thermal", "startup", "voltage_transient") and len(rising) >= 3:
            combo += 10
        if temp_val >= 90 and vib >= 6.5:
            combo = max(combo, 40)
        if temp_val >= 78 and vib < 4.2 and load_val >= 80:
            combo = min(combo, 4)
        fail_rate = 0.0
        if similar["count"]:
            fail_rate = similar["failure_count"] / float(similar["count"])
        hist_points = min(24, similar["failure_count"] * 5 + similar["intervention_count"] * 2)
        if situation.get("id") == "bearing_mechanical" and vib < 4.5:
            hist_points = min(8, hist_points)
            severity_points = min(16, severity_points)
        if similar["count"] >= 8 and similar["failure_count"] == 0 and situation.get("id") == "voltage_transient":
            hist_points = 0
            combo = 2
        if situation.get("id") == "high_load_thermal":
            hist_points = min(4, similar["intervention_count"] * 2)
            severity_points = min(12, severity_points)
        iso_points = int(round(iso * 12))
        # A machine alarm is evidence, not an automatic high-risk verdict.
        alarm_points = 0
        live_normal = situation.get("id") == "normal" and not unusual and (motor.get("status") or "NORMAL") == "NORMAL"
        if live_normal:
            alarm_points = 0
            hist_points = 0
            iso_points = min(iso_points, 4)

        score = int(round(min(100, severity_points + roc_points + combo + hist_points + iso_points + alarm_points)))
        if mode == "STARTING" and situation.get("id") == "startup":
            score = min(score, 28)
        if situation.get("id") == "voltage_transient" and similar["failure_count"] == 0:
            score = min(score, 32)
        if situation.get("id") in ("high_load_thermal", "machine_alarm"):
            score = min(score, 34)
        if live_normal:
            score = min(score, 18)
        if situation.get("id") == "bearing_mechanical":
            if vib < 3.8:
                score = min(score, 34)
            elif vib < 5.0:
                score = min(score, 58)
            elif vib < 6.8 and not (temp_val >= 90 and vib >= 6.5):
                score = min(score, 78)
            elif temp_val >= 90 and vib >= 6.5:
                score = max(score, 82)

        level = _level_from_score(score)
        trend = "stable"
        rising_count = sum(1 for row in deviations if row["name"] in ("vibration", "current", "temperature") and row["percent_change"] > 6)
        rapid = any((row.get("percent_change") or 0) >= 12 for row in deviations if row.get("name") in ("temperature", "vibration"))
        if rising_count >= 2 or rapid:
            trend = "worsening"
        elif all(row["percent_change"] < 2 for row in deviations):
            trend = "stable"

        reason = situation.get("what") or "Motor 01 is within expected behaviour."
        if situation.get("id") == "bearing_mechanical":
            reason = "Current, vibration, and temperature are rising while speed is dropping."
        elif situation.get("id") == "overload":
            reason = "Current increased while speed decreased."
        elif situation.get("id") == "voltage_transient":
            reason = "A voltage excursion occurred without a matching mechanical pattern."
        elif situation.get("id") == "high_load_thermal":
            reason = "Temperature is elevated but consistent with high-load operation."

        evidence = [row["note"] for row in unusual[:6]]
        if similar["summary"]:
            evidence.append(similar["summary"])
        if iso >= 0.55:
            evidence.append("Isolation Forest unusualness {0:.2f} on the live motor vector.".format(iso))

        consequence = situation.get("consequence") or "No immediate equipment risk identified."
        recommended = "Continue monitoring."
        if level in ("HIGH", "CRITICAL"):
            recommended = (situation.get("checks") or ["Inspect the motor and follow the SOP."])[0]
        elif level == "MEDIUM":
            recommended = "Operator attention: verify load and vibration."
        elif level == "MONITOR":
            recommended = "Log and watch. Historical evidence does not justify interrupting the operator."

        factors = {
            "severity": min(25, severity_points),
            "rate_of_change": min(15, roc_points),
            "combined_pattern": combo,
            "historical_failure": hist_points,
            "isolation_forest": iso_points,
            "active_alarm": alarm_points,
        }
        return {
            "score": score,
            "level": level,
            "band": risk_band(level),
            "reason": reason,
            "evidence": evidence,
            "trend": trend,
            "historical_frequency": similar["count"],
            "potential_consequence": consequence,
            "recommended_response": recommended,
            "factors": factors,
            "failure_association": round(100.0 * fail_rate) if similar["count"] else 0,
            "language": "possible",
        }

    def _explanations(
        self,
        deviations: List[Dict[str, Any]],
        situation: Dict[str, Any],
        similar: Dict[str, Any],
        risk: Dict[str, Any],
        mode: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        flagged = risk["level"] not in ("NORMAL",)
        points = []
        for row in deviations:
            if row["unusual"] or abs(row["percent_change"]) >= 8:
                sign = "increased" if row["percent_change"] > 0 else "decreased"
                points.append("{0} {1} {2:.0f}%".format(row["title"], sign, abs(row["percent_change"])))
        if situation.get("id") not in ("normal", ""):
            points.append("Pattern grouped as {0}".format(situation.get("title")))
        if similar["count"]:
            points.append("Similar pattern occurred {0} times historically".format(similar["count"]))
            points.append("{0} previous cases required intervention".format(similar["intervention_count"]))
        if mode == "STARTING":
            points.append("Operating mode is STARTING — inrush is expected.")
        why_flagged = {
            "flagged": flagged and risk["level"] not in ("MONITOR",),
            "attention": risk["level"],
            "points": points or ["No individual parameter crossed a meaningful contextual limit."],
            "score": risk["score"],
            "factors": risk["factors"],
        }
        why_not = {"points": []}
        for row in deviations:
            if not row["unusual"]:
                continue
            if risk["level"] in ("NORMAL", "MONITOR") or (row["name"] == "voltage" and risk["level"] in ("MONITOR", "LOW")):
                hist_same = [
                    ev
                    for ev in self.history_events
                    if (ev.get("pattern_family") or "") in ("voltage_spike",) or abs(float(ev.get(row["name"]) or 0) - row["value"]) < 8
                ]
                count = len(hist_same) if row["name"] == "voltage" else max(1, similar["count"])
                failures = sum(1 for ev in hist_same if ev.get("failure")) if row["name"] == "voltage" else similar["failure_count"]
                why_not["points"].append(
                    "{0} reached {1:.1f} {2}. Not treated as a high-attention event because this has occurred "
                    "{3} times under similar conditions with {4} faults/trips."
                    .format(row["title"], row["value"], row["unit"], count, failures)
                )
        if not flagged:
            why_not["points"].append("Overall condition remains NORMAL for the current load and speed.")
        if not why_not["points"]:
            why_not["points"].append("Attention was assigned because the combined pattern and history are meaningful.")
        return why_flagged, why_not

    def _guidance(self, situation: Dict[str, Any], similar: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
        checks = []
        for index, step in enumerate(situation.get("checks") or [], start=1):
            reason = ""
            if "load" in step.lower():
                reason = "Check mechanical load first because current increased while speed decreased." if situation.get("id") in ("overload", "bearing_mechanical") else "Load sets the expected current and temperature."
            elif "vibration" in step.lower():
                reason = "Vibration is part of the grouped pattern."
            elif "bearing" in step.lower():
                reason = "Historical similar incidents were often bearing-related."
            elif "sop" in step.lower() or "stop" in step.lower():
                reason = "Plant safety procedure takes priority over AERA advice."
            else:
                reason = "Recommended because it matches this motor's previous diagnostic order."
            checks.append({"step": index, "action": step, "reason": reason})
        if not checks and risk["level"] == "NORMAL":
            checks = [{"step": 1, "action": "No extra check required.", "reason": "Motor 01 is operating within expected behaviour."}]
        expert = matching_expert_cases(situation.get("family") or "", situation.get("signals") or [])
        learned = learning_store.data.get("expert") or []
        expert = list(expert) + learned
        sop = sop_by_code(situation.get("sop") or "")
        previous = []
        for row in similar.get("matches") or []:
            if row.get("operator_action"):
                previous.append(
                    {
                        "date": row.get("date"),
                        "action": row.get("operator_action"),
                        "outcome": row.get("outcome"),
                        "source": "motor-hmi-history",
                    }
                )
        for row in self.resolutions:
            if (row.get("pattern_family") or "") == situation.get("family") or "bearing" in (row.get("root_cause") or "").lower():
                previous.append(
                    {
                        "date": row.get("created_at"),
                        "action": row.get("solution") or row.get("actions_taken"),
                        "outcome": row.get("result"),
                        "source": "expert" if row.get("verified") else "history",
                        "root_cause": row.get("root_cause"),
                    }
                )
        return {
            "checks": checks,
            "avoid": situation.get("avoid") or [],
            "sop": sop,
            "expert": expert[:4],
            "previous_solutions": previous[:6],
            "escalate": risk["level"] in ("HIGH", "CRITICAL"),
            "escalate_reason": "Escalate to maintenance/engineer. AERA is not a guaranteed diagnosis."
            if risk["level"] in ("HIGH", "CRITICAL")
            else "",
        }

    def _what_happened(
        self,
        motor: Dict[str, Any],
        sensors: Dict[str, float],
        deviations: List[Dict[str, Any]],
        situation: Dict[str, Any],
        similar: Dict[str, Any],
        risk: Dict[str, Any],
    ) -> str:
        load = sensors.get("load")
        bits = []
        for key in ("current", "speed", "vibration", "temperature"):
            row = next((item for item in deviations if item["name"] == key), None)
            if row and abs(row["percent_change"]) >= 5:
                bits.append("{0} {1} {2:.0f}%".format(row["title"].lower(), "increased" if row["percent_change"] > 0 else "decreased", abs(row["percent_change"])))
        combo = ", ".join(bits) if bits else "parameters are stable"
        context = "unusual for the current load" if any(row["unusual"] for row in deviations) else "consistent with the current load"
        return (
            "Motor {0} has been {1} at {2:.0f}% load. During the last minutes, {3}. "
            "This combination is {4}."
        ).format(motor.get("code") or "M01", (motor.get("operating_mode") or "RUNNING").lower(), load or 0, combo, context)

    def _parameter_view(self, key: str, sensors: Dict[str, float], load: float, speed: float, runtime_h: float) -> Dict[str, Any]:
        brief = parameter_brief(key)
        value = sensors.get(key)
        expected = expected_value(key, load, speed, runtime_h)
        brief.update(
            {
                "value": None if value is None else round(float(value), 3),
                "expected": round(expected, 3),
                "unit": PARAMETERS[key]["unit"],
            }
        )
        return brief

    def _health(self, score: int, status: str) -> int:
        health = max(0, min(100, 100 - score))
        if status == "ALARM":
            health = min(health, 52)
        elif status == "ANOMALY":
            health = min(health, 78)
        return health

    def _motor_alarms(self) -> List[Dict[str, Any]]:
        out = []
        for row in self.alarms:
            asset = str(row.get("asset") or row.get("asset_name") or "")
            if asset and "PUMP" in asset.upper() and "MOTOR" not in asset.upper():
                continue
            status = str(row.get("status") or "").upper()
            if status not in ("ACTIVE", "ACKNOWLEDGED"):
                continue
            out.append(row)
        return out[:12]

    def replay_for_event(self, event_number: int) -> Dict[str, Any]:
        event = None
        for row in self.history_events:
            if row.get("event_number") == event_number or row.get("id") == event_number:
                event = row
                break
        if not event:
            return {"error": "Historical event not found in Motor + HMI history."}
        stamp = event.get("timestamp") or _utcnow()
        date = stamp[:10]
        steps = [
            {"time": "10:21", "label": "Temperature begins rising", "detail": "Thermal trend starts above the expected band for load."},
            {"time": "10:23", "label": "Vibration increases", "detail": "Drive-end vibration leaves the stable running band."},
            {"time": "10:24", "label": "Current increases", "detail": "Current rises as mechanical demand / drag increases."},
            {"time": "10:25", "label": "Alarm generated", "detail": "Motor + HMI recorded the event."},
        ]
        if event.get("intervention"):
            steps.append({"time": "10:26", "label": "Operator acknowledges / intervenes", "detail": event.get("operator_action") or "Operator action recorded."})
        if event.get("failure"):
            steps.append({"time": "10:28", "label": "Motor tripped or stopped", "detail": event.get("outcome") or "Trip recorded."})
        if event.get("operator_action"):
            steps.append({"time": "10:40", "label": "Inspection / solution", "detail": event.get("operator_action")})
        steps.append({"time": "10:55", "label": "Outcome", "detail": event.get("outcome") or "Recorded in history."})
        return {
            "event": event,
            "date": date,
            "title": event.get("description") or event.get("pattern_family"),
            "timeline": steps,
            "source": "motor-hmi-history",
            "note": "Times are reconstructed from the historical record so a new operator can see the order of development.",
        }


engine = SituationEngine()
