"""Safe What-If estimates. Never sends a motor command."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from engine.motor_model import (
    live_snapshot,
    operating_margins,
    predict_operating_point,
    risk_from_condition,
)
from engine.recommend import risk_band


def _num(text: str, key: str) -> Optional[float]:
    match = re.search(rf"{key}[^0-9]{{0,18}}(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def _celsius(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*c\b", text)
    return float(match.group(1)) if match else None


def _mms(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*mm", text)
    return float(match.group(1)) if match else None


def _direction(q: str) -> int:
    if any(token in q for token in ("reduce", "decrease", "lower", "drop", "stop increasing")):
        return -1
    if any(token in q for token in ("increase", "raise", "goes above", "go above", "reaches", "reach", "keep increasing", "rising", "goes to", "go to")):
        return 1
    return 0


def hypothesis_from_question(question: str, sensors: Dict[str, float], topic: str = "") -> Dict[str, Any]:
    q = (question or "").lower()
    live_load = float(sensors.get("load") or 64.0)
    hypo: Dict[str, Any] = {
        "load": sensors.get("load"),
        "speed": sensors.get("speed_setpoint") or sensors.get("speed"),
        "voltage": sensors.get("voltage"),
        "cooling": 1.0,
        "duration_min": 15.0,
        "stopped": False,
        "abrupt": False,
        "hold": False,
        "focus": "",
    }
    if any(token in q for token in ("stop the motor", "if i stop", "if the motor is stopped", "shut down", "if i shut")):
        hypo["stopped"] = True
        hypo["load"] = 0.0
        hypo["focus"] = "stop"
        return hypo
    if any(token in q for token in ("keep running", "keep it running", "if i don't", "if i do not", "continue operating", "don't stop", "do not stop", "if i keep")):
        hypo["hold"] = True
        hypo["focus"] = "hold"
        hypo["duration_min"] = 15.0
        return hypo

    load = _num(q, "load")
    if load is None:
        match = re.search(r"(?:to|at)\s+(\d{2,3})\s*%", q)
        load = float(match.group(1)) if match else None
    speed = _num(q, "speed") or _num(q, "rpm")
    voltage = _num(q, "voltage")
    temperature = _num(q, "temperature") or _num(q, "temp") or _celsius(q)
    vibration = _num(q, "vibration") or _num(q, "vib") or _mms(q)
    current = _num(q, "current") if "current" in q and "load" not in q else None

    direction = _direction(q)
    mentions_load = "load" in q
    mentions_temp = "temperature" in q or " temp" in q or q.startswith("temp")
    mentions_vib = "vibration" in q or "vib" in q
    mentions_rpm = "rpm" in q or "speed" in q
    mentions_volt = "voltage" in q or "volt" in q
    mentions_current = "current" in q or "amps" in q
    mentioned = any((mentions_load, mentions_temp, mentions_vib, mentions_rpm, mentions_volt, mentions_current))

    if load is None and mentions_load and direction:
        load = min(100.0, live_load + 20.0) if direction > 0 else max(20.0, live_load - 20.0)
    if temperature is None and mentions_temp and direction:
        live = float(sensors.get("temperature") or 62.0)
        temperature = min(105.0, live + 12.0) if direction > 0 else max(40.0, live - 8.0)
    if vibration is None and mentions_vib and direction:
        live = float(sensors.get("vibration") or 2.8)
        vibration = min(12.0, max(7.0, live + 4.0)) if direction > 0 else max(0.8, live * 0.6)
    if speed is None and mentions_rpm and direction:
        live = float(sensors.get("speed") or 1450.0)
        speed = min(1800.0, live + 80.0) if direction > 0 else max(400.0, live - 80.0)
    if voltage is None and mentions_volt and direction:
        live = float(sensors.get("voltage") or 232.0)
        voltage = min(280.0, live + 18.0) if direction > 0 else max(160.0, live - 18.0)
    if current is None and mentions_current and direction and not mentions_load:
        live = float(sensors.get("current") or 10.2)
        current = min(22.0, live + 3.0) if direction > 0 else max(0.5, live - 2.0)

    if not mentioned and direction and topic in ("temperature", "vibration", "load", "speed", "voltage", "current"):
        if topic == "load":
            load = min(100.0, live_load + 20.0) if direction > 0 else max(20.0, live_load - 20.0)
            mentions_load = True
        elif topic == "temperature":
            live = float(sensors.get("temperature") or 62.0)
            temperature = min(105.0, live + 12.0) if direction > 0 else max(40.0, live - 8.0)
        elif topic == "vibration":
            live = float(sensors.get("vibration") or 2.8)
            vibration = min(12.0, max(7.0, live + 4.0)) if direction > 0 else max(0.8, live * 0.6)
        elif topic == "speed":
            live = float(sensors.get("speed") or 1450.0)
            speed = min(1800.0, live + 80.0) if direction > 0 else max(400.0, live - 80.0)

    if load is not None:
        hypo["load"] = load
        hypo["abrupt"] = abs(load - live_load) >= 25
        hypo["focus"] = "load"
    if speed is not None:
        hypo["speed"] = speed
        hypo["focus"] = hypo.get("focus") or "speed"
    if voltage is not None:
        hypo["voltage"] = voltage
        hypo["focus"] = hypo.get("focus") or "voltage"
    if temperature is not None:
        hypo["temperature"] = temperature
        hypo["focus"] = hypo.get("focus") or "temperature"
    if vibration is not None:
        hypo["vibration"] = vibration
        hypo["focus"] = hypo.get("focus") or "vibration"
    if current is not None:
        hypo["current"] = current
        hypo["focus"] = hypo.get("focus") or "current"

    if "cooling fail" in q or "cooling failure" in q or "no cooling" in q:
        hypo["cooling"] = 0.35
        hypo["focus"] = hypo.get("focus") or "cooling"
    if "restricted cool" in q:
        hypo["cooling"] = 0.55

    minutes = _num(q, "minute") or _num(q, "min")
    hours = _num(q, "hour")
    if minutes is not None:
        hypo["duration_min"] = load_time_minutes(minutes, "min")
    elif hours is not None:
        hypo["duration_min"] = hours * 60.0

    if not hypo.get("focus"):
        hypo["hold"] = True
        hypo["focus"] = "hold"
    return hypo


def load_time_minutes(value: float, kind: str) -> float:
    return value if kind == "min" else value


def _impact(delta: float, medium: float, high: float) -> str:
    mag = abs(delta)
    if mag >= high:
        return "HIGH"
    if mag >= medium:
        return "MEDIUM"
    if mag >= medium * 0.25:
        return "LOW"
    return "STABLE"


def _trend(delta: float, eps: float = 0.05) -> str:
    if delta > eps:
        return "up"
    if delta < -eps:
        return "down"
    return "flat"


def _comparison(current: Dict[str, float], predicted: Dict[str, float]) -> List[Dict[str, Any]]:
    specs = [
        ("load", "%", 8, 20),
        ("speed", "RPM", 20, 60),
        ("current", "A", 1.2, 3.0),
        ("power", "kW", 0.4, 1.2),
        ("temperature", "°C", 4, 10),
        ("vibration", "mm/s", 0.6, 1.5),
        ("torque", "Nm", 2, 6),
        ("efficiency", "%", 3, 8),
        ("voltage", "V", 6, 14),
    ]
    rows = []
    for key, unit, medium, high in specs:
        before = float(current.get(key) or 0)
        after = float(predicted.get(key) or 0)
        delta = after - before
        rows.append(
            {
                "parameter": key,
                "unit": unit,
                "current": round(before, 2),
                "predicted": round(after, 2),
                "change": round(delta, 3),
                "impact": _impact(delta, medium, high),
                "trend": _trend(delta),
            }
        )
    return rows


def _chain(current: Dict[str, float], predicted: Dict[str, float], hypo: Dict[str, Any]) -> List[str]:
    steps = []
    if hypo.get("stopped"):
        return [
            "Operator hypothesizes a stop",
            "Torque and current demand fall to idle",
            "Electrical power falls",
            "Temperature cools with thermal inertia",
            "Mechanical vibration collapses with rotation",
            "Process throughput stops",
        ]
    d_load = predicted["load"] - current["load"]
    if abs(d_load) >= 1:
        steps.append("Load {0:.0f}% → {1:.0f}%".format(current["load"], predicted["load"]))
        steps.append("Torque demand {0}".format("increases" if d_load > 0 else "decreases"))
    else:
        steps.append("Load held near {0:.0f}%".format(predicted["load"]))
    steps.append("Current demand {0:.1f} → {1:.1f} A".format(current["current"], predicted["current"]))
    steps.append("Electrical power {0:.2f} → {1:.2f} kW".format(current["power"], predicted["power"]))
    steps.append("Temperature moves toward {0:.0f}°C with thermal inertia".format(predicted["temperature"]))
    steps.append("Vibration {0:.1f} → {1:.1f} mm/s".format(current["vibration"], predicted["vibration"]))
    if predicted["efficiency"] < current.get("efficiency", 90) - 1:
        steps.append("Efficiency decreases at the new operating point")
    steps.append("Operating margin is re-evaluated against Motor 01 capability")
    return steps


def _why(
    current: Dict[str, float],
    predicted: Dict[str, float],
    margins: Dict[str, Any],
    before_score: int,
    after_score: int,
    after_level: str,
    factors: Dict[str, int],
    similar: Dict[str, Any],
    hypo: Dict[str, Any],
) -> str:
    parts = []
    d_load = predicted["load"] - current["load"]
    if hypo.get("stopped"):
        parts.append("Stopping removes electrical and mechanical load. Temperature is expected to fall gradually, not instantly.")
    elif d_load > 1:
        parts.append(
            "Load increased from {0:.0f}% to {1:.0f}%, increasing torque and current demand.".format(current["load"], predicted["load"])
        )
    elif d_load < -1:
        parts.append(
            "Reducing load from {0:.0f}% to {1:.0f}% is expected to decrease thermal and mechanical stress and restore operating margin.".format(
                current["load"], predicted["load"]
            )
        )
    else:
        parts.append("Load is essentially unchanged; the estimate is the evolution of the current operating point over time.")
    if margins["power"]["margin"] <= 0.35:
        parts.append(
            "Required power {0:.2f} kW is close to available capability {1:.2f} kW.".format(
                margins["power"]["required"], margins["power"]["available"]
            )
        )
    if predicted["voltage"] < 210:
        parts.append("Lower voltage reduces torque capability and is expected to increase current and heating for the same load.")
    if predicted.get("cooling", 1) < 0.6:
        parts.append("Reduced cooling slows heat rejection, so temperature continues to climb even if load is only moderate.")
    if predicted.get("bearing", 0) >= 0.2:
        parts.append("The live motor already shows mechanical degradation, so the same load is more severe than on a healthy machine.")
    if hypo.get("abrupt") and d_load >= 25:
        parts.append("Risk increased because the load change is abrupt.")
    match = (similar.get("matches") or [None])[0]
    if match:
        parts.append(
            "The predicted operating condition resembles {0} ({1}% similar).".format(
                match.get("root_cause") or "a previous Motor 01 incident", match.get("similarity")
            )
        )
    parts.append("Predicted attention {0} ({1}/100) versus live {2}/100. This is an estimate, not a guaranteed outcome.".format(after_level, after_score, before_score))
    return " ".join(parts)


def _outcome(predicted: Dict[str, float], level: str, hypo: Dict[str, Any]) -> str:
    if hypo.get("stopped"):
        return "The line would stop. Residual heat is expected to fall over several minutes. AERA will not issue the stop."
    if level == "CRITICAL":
        return "If maintained, the motor is likely to enter a region consistent with overload or developing mechanical damage. A controlled review of load and bearing condition is the expected next consideration."
    if level == "HIGH":
        return "If maintained for an extended period, the motor may experience increasing temperature and vibration, with elevated mechanical and electrical stress."
    if level == "MEDIUM":
        return "Operation may remain stable, but thermal and electrical margins are expected to shrink. Continue watching current, temperature, and vibration."
    if level == "MONITOR":
        return "The predicted point stays inside a usable operating region. AERA would keep monitoring rather than interrupt."
    return "The motor is expected to remain well below its available capacity under this hypothesis."


def _history_for_predicted(predicted: Dict[str, float], family: str) -> Dict[str, Any]:
    try:
        from engine.pipeline import engine

        trends = {
            "vibration": 1 if predicted["vibration"] > 3.5 else 0,
            "temperature": 1 if predicted["temperature"] > 68 else 0,
            "current": 1 if predicted["current"] > 11 else 0,
            "speed": -1 if predicted["speed"] < 1420 else 0,
        }
        return engine._similar_incidents(
            {
                "vibration": predicted["vibration"],
                "temperature": predicted["temperature"],
                "current": predicted["current"],
                "speed": predicted["speed"],
                "voltage": predicted["voltage"],
            },
            trends,
            family,
            live_event=True,
        )
    except Exception:
        return {"count": 0, "failure_count": 0, "matches": [], "summary": ""}


def _family(predicted: Dict[str, float]) -> str:
    if predicted.get("bearing", 0) >= 0.2 and predicted["vibration"] >= 4.0:
        return "motor_bearing_failure"
    if predicted["current"] >= 13 and predicted["speed"] < 1420:
        return "motor_overload"
    if predicted["temperature"] >= 78:
        return "motor_overheat"
    return ""


def format_operator_answer(
    current: Dict[str, float],
    predicted: Dict[str, float],
    hypo: Dict[str, Any],
    before_level: str,
    after_level: str,
    similar: Dict[str, Any],
) -> str:
    before_band = risk_band(before_level)
    after_band = risk_band(after_level)
    live_risk = "RISK: {0}".format(before_band)
    pred_risk = "Predicted RISK: {0}".format(after_band)
    if hypo.get("stopped"):
        return "\n".join(
            [
                "WHAT-IF ANALYSIS",
                "",
                "If you stop the motor:",
                "RPM → 0",
                "Current → near zero",
                "Load → 0",
                "Temperature → gradually decreases",
                "Vibration → should decrease",
                "",
                "The active operating stress should ease once the motor is stopped.",
                "If an alarm persisted after stopping, that would indicate the issue may not be purely load-related.",
                "",
                "This is a simulation. The live motor has not been changed.",
            ]
        )
    if hypo.get("hold"):
        lines = [
            "WHAT-IF ANALYSIS",
            "",
            "If you keep running at the current condition:",
            "Temperature: {0:.1f}°C → about {1:.1f}°C".format(current["temperature"], predicted["temperature"]),
            "Vibration: {0:.1f} → about {1:.1f} mm/s".format(current["vibration"], predicted["vibration"]),
            "Load: {0:.0f}%".format(current["load"]),
            "",
            "Current {0}".format(live_risk),
            pred_risk,
        ]
        if after_band in ("HIGH", "CRITICAL"):
            lines.append("Continuing operation increases thermal/mechanical stress. I do not recommend remaining at this condition.")
            lines.append("If an immediate stop is not possible: reduce load and monitor temperature and vibration.")
        elif after_band == "MEDIUM":
            lines.append("Operation may continue with monitoring. Watch temperature and vibration.")
        else:
            lines.append("Based on the current readings, continued operation remains acceptable. I will keep watching.")
        lines.extend(["", "This is a simulation. The live motor has not been changed."])
        return "\n".join(lines)

    focus = hypo.get("focus") or "load"
    units = {"load": "%", "temperature": "°C", "vibration": "mm/s", "speed": "RPM", "voltage": "V", "current": "A"}
    live_focus = current.get("speed" if focus == "speed" else focus, current.get("load"))
    pred_focus = predicted.get("speed" if focus == "speed" else focus, predicted.get("load"))
    lines = [
        "WHAT-IF ANALYSIS",
        "",
        "Current {0}: {1} {2}".format(focus, _fmt(live_focus, focus), units.get(focus, "")).strip(),
        "Requested {0}: {1} {2}".format(focus, _fmt(pred_focus, focus), units.get(focus, "")).strip(),
        "",
        "EXPECTED EFFECT",
        "Current: {0:.1f} → {1:.1f} A ({2})".format(current["current"], predicted["current"], _word(predicted["current"] - current["current"])),
        "Temperature: {0:.1f} → {1:.1f} °C ({2})".format(current["temperature"], predicted["temperature"], _word(predicted["temperature"] - current["temperature"])),
        "Vibration: {0:.1f} → {1:.1f} mm/s ({2})".format(current["vibration"], predicted["vibration"], _word(predicted["vibration"] - current["vibration"])),
        "",
        "{0} → {1}".format(live_risk, pred_risk),
    ]
    why_bits = []
    if focus == "load":
        why_bits.append("Higher load typically increases current, power demand, and temperature.")
    elif focus == "temperature":
        why_bits.append("Higher temperature increases thermal stress and cooling demand. Efficiency may decrease.")
    elif focus == "vibration":
        why_bits.append("Higher vibration is consistent with mechanical imbalance, bearing condition, or alignment stress.")
    elif focus == "speed":
        why_bits.append("Higher RPM increases mechanical operating speed and may increase vibration and thermal effects.")
    elif focus == "voltage":
        why_bits.append("Voltage outside the configured range can increase electrical stress and heating.")
    elif focus == "current":
        why_bits.append("Higher current increases electrical and thermal stress.")
    if similar.get("count"):
        why_bits.append(
            "Similar conditions occurred {0} times previously. {1} required intervention.".format(
                similar.get("count"), similar.get("intervention_count") or 0
            )
        )
    if why_bits:
        lines.append("")
        lines.append("WHY")
        lines.extend(why_bits)
    lines.append("")
    lines.append("RECOMMENDATION")
    if after_band in ("HIGH", "CRITICAL"):
        if focus == "load":
            lines.append("I recommend not increasing the load further from the current starting condition.")
        else:
            lines.append("Avoid operating at this predicted point. Use the HMI only if a real change is required.")
    elif after_band == "MEDIUM":
        lines.append("If you make this change, do it gradually and monitor temperature and vibration.")
    else:
        lines.append("At the current starting condition this remains within an acceptable range. Monitor the response.")
    lines.extend(["", "This is a simulation. The live motor has not been changed."])
    return "\n".join(lines)


def _fmt(value: Any, key: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if key in ("load", "speed"):
        return "{0:.0f}".format(number)
    return "{0:.1f}".format(number)


def _word(delta: float) -> str:
    if delta > 0.15:
        return "likely increases"
    if delta < -0.15:
        return "likely decreases"
    return "may stay similar"


def estimate(assessment: Dict[str, Any], hypothesis: Optional[Dict[str, Any]] = None, question: str = "", topic: str = "") -> Dict[str, Any]:
    sensors = dict(assessment.get("sensors") or {})
    motor = dict(assessment.get("motor") or {})
    situation = assessment.get("situation") or {}
    if not sensors:
        return {
            "banner": "SIMULATION ONLY",
            "command_sent": False,
            "error": "No live Motor 01 sample is available. AERA will not invent a baseline.",
            "title": "What-If unavailable",
            "impact": "UNKNOWN",
            "effects": [],
            "narrative": "Connect the Motor + HMI backend before running a What-If estimate.",
            "recommended": "Restore the Motor + HMI connection.",
        }

    hypo = dict(hypothesis or {})
    if question and not hypothesis:
        hypo = hypothesis_from_question(question, sensors, topic=topic)
    hypo.setdefault("load", sensors.get("load"))
    hypo.setdefault("speed", sensors.get("speed_setpoint") or sensors.get("speed"))
    hypo.setdefault("voltage", sensors.get("voltage"))
    hypo.setdefault("cooling", 1.0)
    hypo.setdefault("duration_min", 15.0)
    if hypo.get("abrupt") is None:
        hypo["abrupt"] = abs(float(hypo.get("load") or 0) - float(sensors.get("load") or 0)) >= 25

    current = live_snapshot(sensors)
    predicted = predict_operating_point(sensors, motor, hypo, situation)
    family = _family(predicted)
    similar = _history_for_predicted(predicted, family)
    margins = operating_margins(predicted, float(predicted["voltage"]))
    before = int((assessment.get("risk") or {}).get("score") or 0)
    after, level, factors, _mode = risk_from_condition(
        predicted,
        margins,
        before,
        assessment.get("health"),
        similar,
        hypo,
        sensors,
    )
    comparison = _comparison(current, predicted)
    why = _why(current, predicted, margins, before, after, level, factors, similar, hypo)
    timeline = []
    for minutes in (5, 15, 30, 60):
        h = dict(hypo)
        h["duration_min"] = minutes
        point = predict_operating_point(sensors, motor, h, situation)
        m = operating_margins(point, float(point["voltage"]))
        score, lvl, _, _ = risk_from_condition(point, m, before, assessment.get("health"), similar, h, sensors)
        timeline.append(
            {
                "minutes": minutes,
                "temperature": point["temperature"],
                "vibration": point["vibration"],
                "current": point["current"],
                "risk_score": score,
                "level": lvl,
            }
        )

    effects = [
        {"parameter": row["parameter"], "change": "{0:+.2f} {1}".format(row["change"], row["unit"])}
        for row in comparison
        if row["parameter"] in ("current", "power", "temperature", "vibration", "torque", "efficiency")
    ]
    recommended = "No control command is sent. Use the Motor + HMI if a real action is required."
    if risk_band(level) in ("HIGH", "CRITICAL") and not hypo.get("stopped"):
        recommended = "I recommend not making this change on the live motor. This is a simulation only."
    title = "If Motor 01 is stopped" if hypo.get("stopped") else "Predicted Motor 01 condition"
    factor_delta = [{ "label": key.replace("_", " "), "points": value} for key, value in factors.items() if value]
    live_level = (assessment.get("risk") or {}).get("level") or "NORMAL"
    operator = format_operator_answer(current, predicted, hypo, live_level, level, similar)

    return {
        "banner": "SIMULATION ONLY",
        "title": title,
        "command_sent": False,
        "note": "AERA cannot start, stop, or reset Motor 01. Predicted values are estimates from the Motor 01 model.",
        "hypothesis": {
            "load": hypo.get("load"),
            "speed": hypo.get("speed"),
            "voltage": hypo.get("voltage"),
            "frequency": hypo.get("frequency"),
            "cooling": hypo.get("cooling"),
            "duration_min": hypo.get("duration_min"),
            "stopped": bool(hypo.get("stopped")),
            "abrupt": bool(hypo.get("abrupt")),
        },
        "current": current,
        "predicted": predicted,
        "comparison": comparison,
        "margins": margins,
        "risk": {
            "before": before,
            "score": after,
            "level": level,
            "factors": factors,
            "contributors": factor_delta,
        },
        "history": {
            "count": similar.get("count") or 0,
            "summary": similar.get("summary") or "No comparable Motor 01 incident found for this predicted vector.",
            "matches": similar.get("matches") or [],
        },
        "chain": _chain(current, predicted, hypo),
        "why": why,
        "expected_outcome": _outcome(predicted, level, hypo),
        "timeline": timeline,
        "effects": effects,
        "impact": level,
        "narrative": operator,
        "recommended": recommended,
        "operator_answer": operator,
        "simulation": True,
    }


def simulate(question: str, assessment: Dict[str, Any], topic: str = "") -> Dict[str, Any]:
    """Backward-compatible copilot entry: parse language, then run the motor model."""
    return estimate(assessment, question=question, topic=topic)
