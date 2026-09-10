"""AERA copilot language layer.

Uses live motor/HMI/assessment context. Never decides risk. Never controls the motor.
Never invents sensor values, history counts, or alarm states.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from engine.events import event_log
from engine.recommend import attention_label, constraint_reply, is_constraint, rec_state, risk_band
from knowledge.history_data import average_resolution_minutes
from knowledge.motor import PARAMETERS, expected_value, parameter_brief

UNITS = {
    "temperature": "°C",
    "vibration": "mm/s",
    "speed": "RPM",
    "rpm": "RPM",
    "current": "A",
    "voltage": "V",
    "load": "%",
    "power": "kW",
}


class CopilotMemory:
    def reset(self) -> None:
        self.turns: List[Dict[str, str]] = []
        self.last_intent = ""
        self.last_topic = ""
        self.completed: List[str] = []

    def __init__(self) -> None:
        self.reset()

    def remember(self, intent: str, topic: str, question: str, answer: str) -> None:
        self.last_intent = intent
        if topic:
            self.last_topic = topic
        self.turns.append({"role": "operator", "text": question, "intent": intent})
        self.turns.append({"role": "aera", "text": answer, "intent": intent})
        self.turns = self.turns[-16:]


memory = CopilotMemory()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _num(value: Any, digits: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if digits == 0:
        return str(int(round(number)))
    return "{0:.{1}f}".format(number, digits)


def _sensor(ctx: Dict[str, Any], key: str) -> float:
    machine = ctx.get("machine") or {}
    if key == "speed":
        key = "rpm"
    try:
        return float(machine.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _series_values(ctx: Dict[str, Any], key: str) -> List[float]:
    rows = ((ctx.get("trends") or {}).get(key) or [])
    out = []
    for row in rows:
        if isinstance(row, dict) and "v" in row:
            out.append(float(row["v"]))
        elif isinstance(row, (int, float)):
            out.append(float(row))
    return out


def _trend_line(ctx: Dict[str, Any], key: str) -> Tuple[str, Optional[float], Optional[float]]:
    values = _series_values(ctx, key)
    if len(values) < 3:
        return "insufficient", None, None
    start, end = values[0], values[-1]
    span = max(abs(start), 1.0)
    delta = end - start
    if abs(delta) / span < 0.03 and abs(delta) < 0.15:
        return "stable", start, end
    if delta > 0:
        return "rising", start, end
    return "falling", start, end


def build_context(assessment: Dict[str, Any]) -> Dict[str, Any]:
    sensors = assessment.get("sensors") or {}
    motor = assessment.get("motor") or {}
    copilot = assessment.get("copilot_view") or {}
    rec = assessment.get("recommendation") or copilot.get("recommendation") or {}
    similar = assessment.get("similar") or {}
    alarms = assessment.get("alarms") or []
    events = assessment.get("events") or []
    deviations = assessment.get("deviations") or []
    return {
        "machine": {
            "id": motor.get("code") or "MOTOR-01",
            "mode": motor.get("status") or "UNKNOWN",
            "health": motor.get("health_status") or "NORMAL",
            "temperature": sensors.get("temperature"),
            "vibration": sensors.get("vibration"),
            "voltage": sensors.get("voltage"),
            "current": sensors.get("current"),
            "rpm": sensors.get("speed"),
            "load": sensors.get("load"),
            "power": sensors.get("power"),
        },
        "alarms": alarms,
        "currentRisk": attention_label((assessment.get("risk") or {}).get("level")),
        "riskBand": (assessment.get("risk") or {}).get("band") or risk_band((assessment.get("risk") or {}).get("level")),
        "riskScore": (assessment.get("risk") or {}).get("score"),
        "currentAssessment": copilot,
        "situation": assessment.get("situation") or {},
        "activeAnomalies": [row for row in deviations if row.get("unusual")],
        "deviations": deviations,
        "recentEvents": events[:40],
        "trends": assessment.get("series") or {},
        "historicalMatches": similar.get("matches") or [],
        "similar": similar,
        "recommendations": rec,
        "operatorInteractions": [row for row in events if row.get("source") in ("OPERATOR", "AERA")],
        "connected": bool(assessment.get("connected")),
        "timestamp": assessment.get("timestamp"),
        "guidance": assessment.get("guidance") or {},
        "parameters": assessment.get("parameters") or {},
        "timeline": assessment.get("timeline") or [],
        "raw": assessment,
    }


def _topic_from_question(q: str) -> str:
    for key, aliases in (
        ("vibration", ("vibration", "vib", "bearing")),
        ("temperature", ("temperature", "temp", "hot", "overheat")),
        ("load", ("load",)),
        ("current", ("current", "amp")),
        ("voltage", ("voltage", "volt", "supply")),
        ("speed", ("rpm", "speed")),
        ("alarm", ("alarm",)),
        ("risk", ("risk", "alert", "serious")),
    ):
        if any(token in q for token in aliases):
            return key
    return ""


def _classify(q: str) -> str:
    if is_constraint(q) and not q.startswith("what if") and "what happens if" not in q:
        return "constraint"
    if q in ("done", "done.", "i did that", "completed", "inspection done", "already did that"):
        return "done"
    if any(
        token in q
        for token in (
            "what happens if",
            "what-if",
            "what if",
            "what will happen",
            "if i increase",
            "if i reduce",
            "if i stop",
            "if i keep",
            "if i don't",
            "if i do not",
            "should i increase",
            "should i reduce",
            "if vibration",
            "if the temperature",
            "if temperature",
            "if i raise",
        )
    ):
        return "whatif"
    if any(token in q for token in ("during this run", "run summary", "handover", "what happened during", "shift summary")):
        return "handover"
    if any(token in q for token in ("quick summary", "give me a summary", "summarize", "status summary")):
        return "summary"
    if q in ("how is the motor?", "how's the motor?", "how is the motor", "is everything okay?", "is everything ok?", "is everything okay", "status", "status?"):
        return "how_is"
    if "how is the motor" in q or "everything okay" in q or "everything ok" in q or "motor okay" in q or "is the motor ok" in q:
        return "how_is"
    if any(token in q for token in ("happened before", "has this happened", "last time", "previous incident", "how many times", "what action worked", "successful action", "how long did it take")):
        return "history"
    if "concerning" in q or "should i worry" in q or "anything i should" in q or any(token in q for token in ("what's wrong", "what is wrong", "why is it showing red", "why red")):
        return "whats_wrong"
    if q == "what happened" or q == "what happened?":
        return "whats_wrong"
    if "why isn't this high risk" in q or "why isnt this high risk" in q or "even though there is an alarm" in q or "despite the alarm" in q or "not high risk even though" in q:
        return "why_not_high"
    if "why is the risk" in q or "why high risk" in q or "why are you calling this high" in q or "why is this high" in q:
        return "why_risk"
    if any(token in q for token in ("what does this alarm", "alarm mean", "why did the alarm", "why the alarm", "explain the alarm")):
        return "alarm"
    if q in ("why?", "why", "explain this", "explain this.", "explain"):
        return "why"
    if "why did" in q or "why has" in q or "why the temperature" in q:
        return "why_happened"
    if q.startswith("why ") or q.startswith("why?"):
        return "why"
    if "increased the load" in q or "after i" in q or "after the load" in q or "what happened after" in q:
        return "after_change"
    if any(token in q for token in ("what changed", "which parameter changed", "what did i change")):
        return "what_changed"
    if any(token in q for token in ("when did this start", "how long has", "how long has this", "what happened before")):
        return "when"
    if any(token in q for token in ("getting worse", "is it worse", "is it getting", "been increasing", "still rising", "improving", "increasing", "rising")):
        return "worse"
    if "5 minutes ago" in q or "few minutes ago" in q or "minutes ago" in q:
        return "minutes_ago"
    if any(token in q for token in ("can i keep", "can i continue", "keep the motor running", "safe to run", "can i keep running", "continue operating", "keep it running")):
        return "keep_running"
    if any(token in q for token in ("what should i do", "what do i do", "check first", "what should i check", "what should i do next", "safest option", "recommended sequence", "should i stop")):
        return "what_to_do"
    if any(token in q for token in ("what should i monitor", "what should i watch")):
        return "monitor"
    if any(token in q for token in ("what could be causing", "likely cause", "possible cause", "what's causing", "what is causing")):
        return "cause"
    if "more important" in q or "prioritize" in q or "which should i" in q or "temperature or vibration" in q:
        return "priority"
    if "what does" in q and any(token in q for token in ("tell me", "mean", "indicate")):
        return "explain_param"
    if "was this expected" in q or "is this expected" in q:
        return "expected"
    if "show me the" in q and "trend" in q:
        return "show_trend"
    if "normal temperature" in q or "normal vibration" in q or "normal rpm" in q:
        return "normal_range"
    if "what happens if i increase the load" in q or "if i increase the load" in q:
        return "whatif"
    param_ask = _param_key(q)
    if param_ask and any(token in q for token in ("okay", "ok", "normal", "current", "what's the", "what is the", "is the")):
        return "param"
    if param_ask and q.endswith("?"):
        return "param"
    return "general"


def _param_key(q: str) -> str:
    if "load" in q:
        return "load"
    if "rpm" in q or "speed" in q:
        return "speed"
    mapping = [
        ("temperature", ("temperature", "temp")),
        ("vibration", ("vibration", "vib")),
        ("voltage", ("voltage", "volt")),
        ("current", ("current", "amps", "amp")),
        ("power", ("power",)),
    ]
    for key, tokens in mapping:
        if any(token in q for token in tokens):
            return key
    return ""


def _status_word(ctx: Dict[str, Any]) -> str:
    return (ctx.get("currentAssessment") or {}).get("status") or ctx.get("currentRisk") or "NORMAL"


def _alert(ctx: Dict[str, Any]) -> bool:
    view = ctx.get("currentAssessment") or {}
    return bool(view.get("alert")) or _status_word(ctx) in ("HIGH RISK", "CRITICAL")


def _how_is(ctx: Dict[str, Any]) -> str:
    mode = (ctx.get("machine") or {}).get("mode") or "UNKNOWN"
    alarms = ctx.get("alarms") or []
    status = _status_word(ctx)
    lines = [
        "Motor is {0}.".format(str(mode).lower()),
        "Temperature: {0}°C.".format(_num(_sensor(ctx, "temperature"))),
        "Vibration: {0} mm/s.".format(_num(_sensor(ctx, "vibration"))),
        "Load: {0}%.".format(_num(_sensor(ctx, "load"), 0)),
        "RPM: {0}.".format(_num(_sensor(ctx, "rpm"), 0)),
    ]
    if alarms:
        top = alarms[0]
        lines.append("Active alarm: {0} ({1} {2}).".format(top.get("title") or "ALARM", top.get("value"), top.get("unit") or ""))
    else:
        lines.append("No active alarms.")
    if status in ("NORMAL", "RESOLVED"):
        lines.append("AERA assessment: NORMAL. No intervention required.")
    else:
        lines.append("AERA assessment: {0}.".format(status))
    lines.append("RISK: {0}.".format(ctx.get("riskBand") or "LOW"))
    return "\n".join(lines)


def _summary(ctx: Dict[str, Any]) -> str:
    alarms = ctx.get("alarms") or []
    anomalies = ctx.get("activeAnomalies") or []
    alarm_line = "None" if not alarms else ", ".join(str(row.get("title") or "ALARM") for row in alarms[:3])
    action = (ctx.get("currentAssessment") or {}).get("action") or "Continue monitoring."
    return "\n".join(
        [
            "MOTOR: {0}".format((ctx.get("machine") or {}).get("mode")),
            "TEMPERATURE: {0}°C".format(_num(_sensor(ctx, "temperature"))),
            "VIBRATION: {0} mm/s".format(_num(_sensor(ctx, "vibration"))),
            "LOAD: {0}%".format(_num(_sensor(ctx, "load"), 0)),
            "ACTIVE ALARMS: {0}".format(alarm_line),
            "AERA ASSESSMENT: {0}".format(_status_word(ctx)),
            "RISK: {0}".format(ctx.get("riskBand") or "LOW"),
            "UNUSUAL PARAMETERS: {0}".format(", ".join(row.get("title") or row.get("name") for row in anomalies[:4]) or "None"),
            "ACTION: {0}".format(action),
        ]
    )


def _whats_wrong(ctx: Dict[str, Any]) -> str:
    status = _status_word(ctx)
    sid = (ctx.get("situation") or {}).get("id")
    load = _sensor(ctx, "load")
    temp = _sensor(ctx, "temperature")
    vib = _sensor(ctx, "vibration")
    if not _alert(ctx) and status in ("NORMAL", "RESOLVED", "ATTENTION"):
        if sid == "high_load_thermal" or (load >= 80 and temp >= 78 and vib < 4.2):
            return (
                "Not currently.\n\n"
                "Temperature is elevated but expected for the current load.\n"
                "Vibration remains normal.\n"
                "No significant anomaly is detected."
            )
        if status in ("NORMAL", "RESOLVED"):
            return "Not currently.\n\n" + _how_is(ctx)
    view = ctx.get("currentAssessment") or {}
    lines = []
    if _alert(ctx):
        lines.append("⚠ ALERT")
        lines.append("")
    lines.append(status)
    lines.append("")
    if view.get("what"):
        lines.append(view["what"])
    if view.get("analysis"):
        lines.append(view["analysis"])
    if view.get("cause"):
        lines.append("Likely cause: {0}".format(view["cause"]))
    if view.get("action"):
        lines.append("Recommended action: {0}".format(view["action"]))
    return "\n".join(lines)


def _alarm(ctx: Dict[str, Any]) -> str:
    alarms = ctx.get("alarms") or []
    sid = (ctx.get("situation") or {}).get("id")
    if not alarms:
        return "There is no active motor alarm right now."
    top = alarms[0]
    status = _status_word(ctx)
    similar = ctx.get("similar") or {}
    lines = [
        "{0}{1}".format("⚠ ALERT\n\n" if _alert(ctx) else "", top.get("title") or "MOTOR ALARM"),
        "",
        "The motor reported this alarm. AERA is interpreting it, not copying it as a verdict.",
        "Value: {0} {1}".format(top.get("value"), top.get("unit") or ""),
        "Condition: {0}".format(top.get("condition") or "Threshold exceeded"),
        "Alarm status: {0}".format(top.get("alarm_status") or top.get("status") or "Active"),
        "Time: {0}".format(top.get("clock") or ""),
        "",
        "AERA assessment: {0}.".format(status),
    ]
    if sid == "high_load_thermal":
        lines.append("This temperature alarm is common during the current high-load operation. Historical outcomes usually did not require intervention.")
        lines.append("Continue monitoring. No immediate stop is indicated.")
    elif similar.get("count"):
        lines.append(
            "Similar conditions occurred {0} times previously. {1} required intervention.".format(
                similar.get("count"), similar.get("intervention_count") or 0
            )
        )
        action = (ctx.get("currentAssessment") or {}).get("action")
        if action:
            lines.append("Recommended action: {0}".format(action))
    return "\n".join(lines)


def _why_risk(ctx: Dict[str, Any]) -> str:
    view = ctx.get("currentAssessment") or {}
    similar = ctx.get("similar") or {}
    vib = _sensor(ctx, "vibration")
    load = _sensor(ctx, "load")
    temp = _sensor(ctx, "temperature")
    band = ctx.get("riskBand") or "LOW"
    direction, start, end = _trend_line(ctx, "vibration")
    temp_dir, t0, t1 = _trend_line(ctx, "temperature")
    lines = [
        "RISK is {0} because:".format(band),
        "",
        "• Temperature is {0}°C.".format(_num(temp)),
        "• Vibration is {0} mm/s.".format(_num(vib)),
        "• Load is {0}%.".format(_num(load, 0)),
    ]
    if start is not None and end is not None and direction == "rising":
        lines.append("• Vibration moved from {0} to {1} mm/s on the live trend.".format(_num(start), _num(end)))
    if t0 is not None and t1 is not None and temp_dir == "rising":
        lines.append("• Temperature is increasing from {0} to {1}°C.".format(_num(t0), _num(t1)))
    if similar.get("count"):
        lines.append(
            "• Similar events occurred {0} times. {1} required operator intervention.".format(
                similar.get("count"), similar.get("intervention_count") or 0
            )
        )
    else:
        lines.append("• I do not have a close historical match count beyond the current pattern grouping.")
    if view.get("cause"):
        lines.append("• Likely cause: {0}".format(view["cause"]))
    return "\n".join(lines)


def _why_not_high(ctx: Dict[str, Any]) -> str:
    alarms = ctx.get("alarms") or []
    sid = (ctx.get("situation") or {}).get("id")
    similar = ctx.get("similar") or {}
    lines = [
        "A motor alarm is raw machine information. AERA does not automatically treat ALARM as HIGH RISK.",
        "",
        "Current assessment: {0}.".format(_status_word(ctx)),
    ]
    if alarms:
        top = alarms[0]
        lines.append("Active alarm: {0} at {1} {2}.".format(top.get("title"), top.get("value"), top.get("unit") or ""))
    if sid == "high_load_thermal" or (_sensor(ctx, "load") >= 80 and _sensor(ctx, "vibration") < 4.2):
        lines.append("Temperature is elevated with high load and vibration is not in the mechanical-fault band.")
        if similar.get("count"):
            lines.append(
                "Similar high-load heating occurred {0} times. {1} required intervention.".format(
                    similar.get("count"), similar.get("intervention_count") or 0
                )
            )
        lines.append("Continue monitoring.")
    else:
        lines.append("Based on load, vibration, trend, and history, this does not currently meet AERA's high-risk combination.")
    return "\n".join(lines)


def _why_happened(ctx: Dict[str, Any]) -> str:
    topic = memory.last_topic or "temperature"
    if topic == "rpm":
        topic = "speed"
    load_events = [row for row in (ctx.get("recentEvents") or []) if row.get("parameter") == "load"]
    vib_events = [row for row in (ctx.get("recentEvents") or []) if row.get("parameter") == "vibration"]
    temp = _sensor(ctx, "temperature")
    vib = _sensor(ctx, "vibration")
    load = _sensor(ctx, "load")
    if load_events:
        newest, oldest = load_events[0], load_events[-1]
        lines = [
            "Temperature is {0}°C and vibration is {1} mm/s after load changed from {2}% to {3}%.".format(
                _num(temp), _num(vib), oldest.get("previous"), newest.get("new")
            )
        ]
        if vib < 4.2 and not _alert(ctx):
            lines.append("Vibration remains normal. Based on the available data, the temperature increase is consistent with the higher load rather than a new abnormality.")
        elif vib >= 4.5:
            lines.append("The simultaneous vibration increase is unusual for this load. This may indicate an additional mechanical issue.")
            lines.append("RISK: {0}.".format(ctx.get("riskBand") or "HIGH"))
        return "\n".join(lines)
    if vib_events:
        return "Vibration changed from {0} to {1} mm/s. Current load is {2}%. RISK: {3}.".format(
            vib_events[-1].get("previous"), vib_events[0].get("new"), _num(load, 0), ctx.get("riskBand") or "LOW"
        )
    direction, start, end = _trend_line(ctx, topic if topic in UNITS else "temperature")
    if start is not None:
        return "{0} moved from {1} to {2} {3} on the live trend. Current load is {4}%.".format(
            topic.title(), _num(start), _num(end), UNITS.get(topic, ""), _num(load, 0)
        )
    return _after_change(ctx)


def _why(ctx: Dict[str, Any]) -> str:
    topic = memory.last_topic
    if topic in ("risk", "alert") or (not topic and _alert(ctx)):
        return _why_risk(ctx)
    if topic == "alarm":
        return _alarm(ctx)
    if topic in ("vibration", "temperature", "current", "load", "speed") and _alert(ctx):
        return _why_risk(ctx) if topic == "vibration" else _whats_wrong(ctx)
    if _alert(ctx):
        return _why_risk(ctx)
    view = ctx.get("currentAssessment") or {}
    bits = [view.get("analysis") or view.get("what") or "Based on the current readings."]
    if view.get("cause"):
        bits.append("Likely cause: {0}".format(view["cause"]))
    if view.get("history"):
        bits.append(view["history"])
    return "\n\n".join(bit for bit in bits if bit)


def _history(ctx: Dict[str, Any]) -> str:
    similar = ctx.get("similar") or {}
    matches = ctx.get("historicalMatches") or []
    count = int(similar.get("count") or 0)
    if not count:
        return (
            "I don't have a close historical match for this exact live combination.\n"
            "I can still assess the current motor condition from live values."
        )
    need = int(similar.get("intervention_count") or 0)
    family = (ctx.get("situation") or {}).get("family") or ""
    minutes = average_resolution_minutes(family) if family else 0
    successful = [
        row.get("operator_action")
        for row in matches
        if row.get("operator_action") and row.get("intervention")
    ]
    lines = [
        "Yes.",
        "",
        "I found {0} similar historical events.".format(count),
        "{0} of those required operator intervention.".format(need),
    ]
    if successful:
        lines.append("The most common successful previous action: {0}".format(successful[0]))
    if minutes:
        lines.append("Average previous resolution time: {0:.0f} minutes.".format(minutes))
    return "\n".join(lines)


def _what_changed(ctx: Dict[str, Any]) -> str:
    events = [
        row
        for row in (ctx.get("recentEvents") or [])
        if row.get("event_kind") == "Parameter Change" or str(row.get("event_type") or "").endswith("_CHANGED")
    ]
    if not events:
        direction_bits = []
        for key in ("temperature", "vibration", "load", "current", "speed"):
            direction, start, end = _trend_line(ctx, key)
            if direction in ("rising", "falling") and start is not None:
                direction_bits.append("{0}: {1} → {2} {3} ({4})".format(key, _num(start), _num(end), UNITS.get(key, ""), direction))
        if not direction_bits:
            return "No significant parameter changes are recorded in the current session yet."
        return "On the live trend:\n\n" + "\n".join(direction_bits)
    lines = ["Recent significant changes:"]
    seen = set()
    unusual = ""
    for row in events[:8]:
        key = row.get("parameter") or row.get("event_type")
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            "{0}: {1} → {2} {3}".format(
                (row.get("parameter") or "parameter").title(),
                row.get("previous"),
                row.get("new"),
                row.get("unit") or "",
            )
        )
        if (row.get("parameter") or "") == "vibration" and float(row.get("new") or 0) >= 5:
            unusual = "The vibration increase is the most unusual change."
    if unusual:
        lines.append("")
        lines.append(unusual)
    return "\n".join(lines)


def _after_change(ctx: Dict[str, Any]) -> str:
    load_events = [row for row in (ctx.get("recentEvents") or []) if row.get("parameter") == "load"]
    if not load_events:
        return _what_changed(ctx)
    newest = load_events[0]
    oldest = load_events[-1]
    prev = oldest.get("previous")
    new = newest.get("new")
    temp_dir, t0, t1 = _trend_line(ctx, "temperature")
    vib_dir, v0, v1 = _trend_line(ctx, "vibration")
    cur_dir, c0, c1 = _trend_line(ctx, "current")
    lines = [
        "After load changed from {0}% to {1}%:".format(prev, new),
        "",
        "Temperature: {0}°C ({1}).".format(_num(_sensor(ctx, "temperature")), temp_dir),
        "Current: {0} A ({1}).".format(_num(_sensor(ctx, "current")), cur_dir),
        "Vibration: {0} mm/s ({1}).".format(_num(_sensor(ctx, "vibration")), vib_dir),
    ]
    if _sensor(ctx, "vibration") < 4.2 and not _alert(ctx):
        lines.append("")
        lines.append("The temperature and current increase are consistent with higher load. No significant abnormality is currently detected.")
    elif _alert(ctx):
        lines.append("")
        lines.append("The vibration response is stronger than expected for this load. RISK remains {0}.".format(_status_word(ctx)))
    return "\n".join(lines)


def _when(ctx: Dict[str, Any]) -> str:
    events = ctx.get("recentEvents") or []
    alarm = next((row for row in events if row.get("event_type") in ("ALARM_TRIGGERED", "ANOMALY_DETECTED")), None)
    if not alarm:
        active = (ctx.get("alarms") or [None])[0]
        if active and active.get("clock"):
            return "The active alarm {0} was recorded at {1}.".format(active.get("title"), active.get("clock"))
        return "I don't have a recorded start time for a current alarm. I can still describe the live values."
    started = _parse_time(alarm.get("timestamp") or "")
    ago = ""
    if started:
        seconds = max(0, int((_now() - started).total_seconds()))
        if seconds < 120:
            ago = " ({0} seconds ago)".format(seconds)
        else:
            ago = " ({0} minutes ago)".format(max(1, seconds // 60))
    before = [row for row in events if row.get("event_kind") == "Parameter Change"]
    lines = ["This condition was recorded at {0}{1}.".format(alarm.get("clock") or "", ago)]
    if before:
        first = before[-1] if before else None
        if first:
            lines.append(
                "Just before that, {0} changed from {1} to {2} {3}.".format(
                    first.get("parameter"), first.get("previous"), first.get("new"), first.get("unit") or ""
                )
            )
    return "\n".join(lines)


def _worse(ctx: Dict[str, Any], named: str = "") -> str:
    topic = named if named in ("vibration", "temperature", "current", "load", "speed") else ""
    if not topic:
        if _sensor(ctx, "vibration") >= 4.5:
            topic = "vibration"
        elif _sensor(ctx, "temperature") >= 80:
            topic = "temperature"
        elif memory.last_intent not in ("constraint", "done") and memory.last_topic in (
            "vibration",
            "temperature",
            "current",
            "load",
            "speed",
        ):
            topic = memory.last_topic
        else:
            topic = "vibration"
    direction, start, end = _trend_line(ctx, topic)
    unit = UNITS.get(topic, "")
    if direction == "insufficient" or start is None:
        return "I don't have a long enough live trend yet to say whether {0} is getting worse.".format(topic)
    if direction == "rising":
        return (
            "Yes.\n\n{0} has increased from {1} to {2} {3} on the live trend.\n"
            "The condition is becoming more significant. RISK remains {4}."
        ).format(topic.title(), _num(start), _num(end), unit, _status_word(ctx))
    if direction == "falling":
        return (
            "No.\n\n{0} is decreasing from {1} to {2} {3}.\n"
            "The previous abnormal condition is improving."
        ).format(topic.title(), _num(start), _num(end), unit)
    return (
        "No.\n\n{0} has remained around {1}–{2} {3} on the live trend.\n"
        "The condition is currently stable, but assessment remains {4}."
    ).format(topic.title(), _num(start), _num(end), unit, _status_word(ctx))


def _minutes_ago(ctx: Dict[str, Any], q: str) -> str:
    key = _param_key(q) or memory.last_topic or "temperature"
    if key == "rpm":
        key = "speed"
    values = _series_values(ctx, key)
    if len(values) < 2:
        return "I don't have enough live samples stored to report {0} from several minutes ago.".format(key)
    return (
        "I keep a short live window (about the last {0} samples), not a full 5-minute archive.\n"
        "In that window {1} moved from {2} to {3} {4}. Current value is {3} {4}."
    ).format(len(values), key, _num(values[0]), _num(values[-1]), UNITS.get(key, ""))


def _keep_running(ctx: Dict[str, Any]) -> str:
    status = _status_word(ctx)
    band = ctx.get("riskBand") or "LOW"
    view = ctx.get("currentAssessment") or {}
    if status in ("HIGH RISK", "CRITICAL") or band in ("HIGH", "CRITICAL"):
        alt = (ctx.get("recommendations") or {}).get("alternative") or view.get("alternative") or []
        lines = [
            "Continuing without a check is not recommended.",
            "",
            "RISK: {0}".format(band),
            view.get("analysis") or "The current combination is unusual versus historical operation.",
        ]
        if alt:
            lines.append("")
            lines.append("If an immediate stop is not possible:")
            for index, step in enumerate(alt[:4], start=1):
                lines.append("{0}. {1}".format(index, step))
        return "\n".join(lines)
    if status == "ATTENTION" or band == "MEDIUM":
        return (
            "You may continue, with monitoring.\n\n"
            "RISK: {0}\n\n"
            "{1}\n\n"
            "Watch vibration and temperature. No stop is required unless the condition worsens."
        ).format(band, view.get("analysis") or "The deviation is currently attention-worthy, not high risk.")
    return (
        "Yes, based on the current condition.\n\n"
        "RISK: {0}\n"
        "The motor is operating within expected conditions.\n"
        "Continue normal operation. I will keep watching."
    ).format(band)


def _what_to_do(ctx: Dict[str, Any]) -> str:
    if "inspection" in " ".join(memory.completed).lower() or "bearing" in " ".join(memory.completed).lower():
        return "Understood — an inspection was already recorded.\n\nContinue monitoring vibration and temperature for improvement. I will not repeat the same inspection recommendation unless the condition worsens."
    view = ctx.get("currentAssessment") or {}
    rec = ctx.get("recommendations") or {}
    checks = (ctx.get("guidance") or {}).get("checks") or []
    status = _status_word(ctx)
    if status in ("NORMAL", "RESOLVED"):
        return "No extra action is required.\n\nContinue normal operation and keep watching the live values."
    lines = ["Recommended sequence:"]
    primary = rec.get("primary") or view.get("action")
    alt = rec.get("alternative") or view.get("alternative") or []
    steps = []
    if primary:
        steps.append(primary)
    steps.extend(list(alt)[:3])
    if not steps:
        steps = [row.get("action") for row in checks[:4] if row.get("action")]
    for index, step in enumerate(steps[:4], start=1):
        lines.append("{0}. {1}".format(index, step))
    lines.append("")
    lines.append("I'll continue evaluating as the machine state changes.")
    if rec.get("actionable"):
        lines.append("If that action is not possible, say so and I will give an alternative.")
    return "\n".join(lines)


def _cause(ctx: Dict[str, Any]) -> str:
    view = ctx.get("currentAssessment") or {}
    sid = (ctx.get("situation") or {}).get("id")
    temp_u = _sensor(ctx, "temperature") >= 80
    vib_u = _sensor(ctx, "vibration") >= 4.5
    load = _sensor(ctx, "load")
    lines = ["Most likely causes based on the current pattern:"]
    if sid == "bearing_mechanical" or (vib_u and load < 80):
        lines.extend(
            [
                "1. Bearing alignment or lubrication issue",
                "2. Mechanical imbalance",
                "3. Increased friction",
                "",
                "The combination of high vibration{0} makes a mechanical issue more likely than simple load-related heating.".format(
                    " and temperature" if temp_u else ""
                ),
            ]
        )
    elif sid == "high_load_thermal" or (temp_u and load >= 80 and not vib_u):
        lines.extend(
            [
                "1. Expected heating from high process load",
                "2. Reduced cooling effectiveness",
                "",
                "Vibration is not in the mechanical-fault band, so this is more consistent with high-load operation.",
            ]
        )
    elif sid == "overload":
        lines.append("1. Increased mechanical load on the driven equipment")
        lines.append("2. Process demand rather than a bearing fault")
    else:
        cause = view.get("cause")
        if cause:
            lines.append("1. {0}".format(cause))
        else:
            return "No abnormal cause is identified from the current live combination."
    lines.append("")
    lines.append("This is a likely/possible interpretation, not a confirmed diagnosis.")
    action = view.get("action")
    if action:
        lines.append("Recommended first check: {0}".format(action))
    return "\n".join(lines)


def _priority(ctx: Dict[str, Any]) -> str:
    rows = []
    for key, label in (("vibration", "Vibration"), ("temperature", "Temperature"), ("current", "Current"), ("voltage", "Voltage")):
        item = next((row for row in (ctx.get("deviations") or []) if row.get("name") == key), None)
        value = _sensor(ctx, "rpm" if key == "speed" else key)
        severity = "Normal"
        if key == "vibration" and value >= 6.5:
            severity = "HIGH RISK"
        elif key == "vibration" and value >= 4.8:
            severity = "ALERT"
        elif key == "temperature" and value >= 90:
            severity = "HIGH RISK"
        elif key == "temperature" and value >= 82:
            severity = "ATTENTION"
        elif item and item.get("unusual"):
            severity = "Monitor"
        rows.append((label, severity, value, UNITS.get(key, "")))
    rank = {"HIGH RISK": 0, "ALERT": 1, "ATTENTION": 2, "Monitor": 3, "Normal": 4}
    rows.sort(key=lambda item: rank.get(item[1], 9))
    lines = ["PRIORITY:"]
    for index, (label, severity, value, unit) in enumerate(rows, start=1):
        lines.append("{0}. {1} — {2} ({3} {4})".format(index, label, severity, _num(value), unit))
    top = rows[0]
    lines.append("")
    lines.append("Start with {0} because it is the highest-priority live condition.".format(top[0].lower()))
    return "\n".join(lines)


def _explain_param(ctx: Dict[str, Any], q: str) -> str:
    key = _param_key(q) or memory.last_topic or "vibration"
    if key == "rpm":
        key = "speed"
    brief = parameter_brief(key)
    value = _sensor(ctx, "rpm" if key == "speed" else key)
    unit = UNITS.get(key, brief.get("unit") or "")
    item = next((row for row in (ctx.get("deviations") or []) if row.get("name") == key), None)
    lines = [
        "{0} indicates {1}".format(brief.get("name") or key, (brief.get("meaning") or "").rstrip(".") + "."),
        "",
        "Current: {0} {1}".format(_num(value, 0 if key in ("speed", "load") else 1), unit),
    ]
    if item:
        lines.append(item.get("note") or "")
    if item and item.get("unusual"):
        lines.append("That is outside the expected band for the current operating condition.")
        action = (ctx.get("currentAssessment") or {}).get("action")
        if action and _alert(ctx):
            lines.append("Recommended action: {0}".format(action))
    else:
        lines.append("That is consistent with the current load and speed.")
    return "\n".join(line for line in lines if line)


def _param(ctx: Dict[str, Any], q: str) -> str:
    key = _param_key(q)
    if not key:
        return _how_is(ctx)
    if key == "rpm":
        key = "speed"
    value = _sensor(ctx, key)
    unit = UNITS.get(key, "")
    load = _sensor(ctx, "load")
    speed = _sensor(ctx, "rpm")
    expected = expected_value(key, load, speed, 0.05)
    item = next((row for row in (ctx.get("deviations") or []) if row.get("name") == key), None)
    if "what's the" in q or "what is the" in q or q.startswith("current "):
        if not any(token in q for token in ("okay", "ok", "normal")):
            return "Current {0}: {1} {2}.".format(key, _num(value, 0 if key in ("speed", "load") else 1), unit)
    unusual = bool(item and item.get("unusual"))
    if not unusual and not _alert(ctx):
        return (
            "Yes. {0} is currently {1} {2} and is within the expected range for the current load ({3}%)."
        ).format(key.title(), _num(value), unit, _num(load, 0))
    sid = (ctx.get("situation") or {}).get("id")
    if sid == "high_load_thermal" and key == "temperature":
        return (
            "ATTENTION\n\n"
            "Temperature is currently {0}°C, which is above the usual running point.\n"
            "This level is common during the current high-load condition.\n"
            "No immediate intervention is recommended. Continue monitoring."
        ).format(_num(value))
    if _alert(ctx):
        return (
            "⚠ ALERT\n\n"
            "{0} is {1} {2}.\n"
            "Expected for the current load is about {3} {2}.\n"
            "RISK: {4}\n\n"
            "{5}"
        ).format(key.title(), _num(value), unit, _num(expected), _status_word(ctx), (ctx.get("currentAssessment") or {}).get("action") or "Inspect the motor.")
    return (
        "ATTENTION\n\n"
        "{0} is {1} {2}. Expected is about {3} {2} at {4}% load.\n"
        "{5}"
    ).format(key.title(), _num(value), unit, _num(expected), _num(load, 0), (item or {}).get("note") or "Continue monitoring.")


def _normal_range(ctx: Dict[str, Any], q: str) -> str:
    key = _param_key(q) or "temperature"
    if key == "rpm":
        key = "speed"
    brief = parameter_brief(key)
    load = _sensor(ctx, "load")
    expected = expected_value(key, load, _sensor(ctx, "rpm"), 0.05)
    return (
        "For this motor at the current {0}% load, {1} is typically around {2} {3}.\n"
        "Live value is {4} {3}.\n"
        "{5}"
    ).format(
        _num(load, 0),
        key,
        _num(expected),
        UNITS.get(key, ""),
        _num(_sensor(ctx, key)),
        brief.get("normal_behaviour") or "",
    )


def _handover(ctx: Dict[str, Any]) -> str:
    events = list(reversed(ctx.get("recentEvents") or []))
    if not events:
        return "No session events are recorded yet. The motor is {0}.".format((ctx.get("machine") or {}).get("mode"))
    first = _parse_time(events[0].get("timestamp") or "")
    minutes = 0
    if first:
        minutes = max(1, int((_now() - first).total_seconds() / 60))
    alarms = [row for row in events if row.get("event_type") == "ALARM_TRIGGERED"]
    anomalies = [row for row in events if row.get("event_type") == "ANOMALY_DETECTED"]
    rejects = [row for row in events if row.get("event_type") == "RECOMMENDATION_REJECTED"]
    returns = [row for row in events if row.get("event_type") == "ALARM_RETURNED"]
    lines = [
        "RUN SUMMARY",
        "",
        "Session events recorded: {0}.".format(len(events)),
        "Approximate observed duration: {0} minute(s).".format(minutes),
        "{0} alarm activation(s). {1} AERA anomaly detection(s).".format(len(alarms), len(anomalies)),
    ]
    if rejects:
        lines.append("Operator rejected at least one recommendation. An alternative was issued.")
    if returns:
        lines.append("{0} alarm return event(s) were recorded.".format(len(returns)))
    if ctx.get("alarms"):
        lines.append("An alarm is still active. Assessment: {0}.".format(_status_word(ctx)))
    else:
        lines.append("No unresolved active alarm at this moment. Assessment: {0}.".format(_status_word(ctx)))
    return "\n".join(lines)


def _monitor(ctx: Dict[str, Any]) -> str:
    if _alert(ctx) or _sensor(ctx, "vibration") >= 4.5:
        return "Monitor vibration first, then temperature and current.\nDo not increase load until vibration settles."
    if _sensor(ctx, "load") >= 80:
        return "During high load, watch temperature and current. Vibration should stay near the normal band. If vibration rises with temperature, treat it as mechanical."
    return "Watch temperature, vibration, and load. I will flag anything that becomes unusual versus history."


def _expected(ctx: Dict[str, Any]) -> str:
    sid = (ctx.get("situation") or {}).get("id")
    if sid == "high_load_thermal":
        return "Yes. Elevated temperature at this load is consistent with previous high-load operation."
    if _alert(ctx):
        return "No. The current combination is unusual compared with historical operation."
    return "Yes. The current values are consistent with the present load and speed."


def _show_trend(ctx: Dict[str, Any], q: str) -> str:
    key = _param_key(q) or memory.last_topic or "temperature"
    if key == "rpm":
        key = "speed"
    direction, start, end = _trend_line(ctx, key)
    values = _series_values(ctx, key)[-8:]
    if not values:
        return "I don't have a live {0} trend stored yet.".format(key)
    path = " → ".join(_num(item) for item in values)
    return (
        "{0} trend ({1}): {2} {3}\n"
        "The live chart under the copilot is the same data. Current point: {4} {3}."
    ).format(key.title(), direction, path, UNITS.get(key, ""), _num(values[-1]))


def _done(ctx: Dict[str, Any]) -> str:
    memory.completed.append("operator reported action completed")
    direction, start, end = _trend_line(ctx, "vibration")
    lines = [
        "Understood. I'll treat the recommended check as completed.",
        "",
        "I'll continue monitoring vibration and temperature for improvement.",
    ]
    if direction == "falling":
        lines.append("Condition is already improving on the live trend ({0} → {1} mm/s).".format(_num(start), _num(end)))
    return "\n".join(lines)


def _general(ctx: Dict[str, Any], q: str) -> str:
    if _alert(ctx):
        return _whats_wrong(ctx)
    if "load" in q and "increase" in q:
        return (
            "If load increases, current and temperature typically rise with it. Vibration should stay near the normal band.\n"
            "Live load is {0}%. I will watch the response if you change it on the HMI."
        ).format(_num(_sensor(ctx, "load"), 0))
    return _how_is(ctx)


def _next_prompt(intent: str, ctx: Dict[str, Any]) -> str:
    if intent == "whats_wrong" and _alert(ctx):
        return "Would you like the previous successful interventions, or an alternative action?"
    if intent == "history" and _alert(ctx):
        return "Would you like the recommended action next?"
    if intent == "what_to_do" and (ctx.get("recommendations") or {}).get("actionable"):
        return "If that action is not possible, say so."
    return ""


def _maybe_llm(question: str, text: str, ctx: Dict[str, Any]) -> Tuple[str, str]:
    if not settings.has_llm:
        return text, "rules"
    compact = {
        "machine": ctx.get("machine"),
        "alarms": [
            {"title": row.get("title"), "value": row.get("value"), "unit": row.get("unit"), "condition": row.get("condition"), "status": row.get("alarm_status") or row.get("status")}
            for row in (ctx.get("alarms") or [])[:4]
        ],
        "assessment": _status_word(ctx),
        "similar_count": (ctx.get("similar") or {}).get("count"),
        "intervention_count": (ctx.get("similar") or {}).get("intervention_count"),
        "recommendation": (ctx.get("currentAssessment") or {}).get("action"),
        "follow_up_topic": memory.last_topic,
    }
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AERA, an industrial copilot. "
                        "Use ONLY the provided machine context and the drafted answer for machine-specific claims. "
                        "Never invent sensor readings, historical event counts, alarm states, or actions. "
                        "Never claim an action was performed unless the draft says so. "
                        "If information is unavailable, say so. "
                        "Keep a calm control-room tone. Be concise. "
                        "When risk is significant, keep ALERT and RISK visible. "
                        "Never silently control the machine."
                    ),
                },
                {
                    "role": "user",
                    "content": "Question: {0}\nContext: {1}\nDraft answer to rephrase, not replace facts:\n{2}".format(
                        question, compact, text
                    ),
                },
            ],
        )
        return completion.choices[0].message.content or text, "llm"
    except Exception:
        return text, "fallback"


def answer(question: str, assessment: Dict[str, Any], experience: str = "NEW") -> Dict[str, Any]:
    q = (question or "").strip()
    if not assessment.get("connected"):
        text = "AERA is not receiving live motor data. It will not invent values."
        return {"answer": text, "source": "fallback", "sections": {"CURRENT STATUS": text}, "simulation": False}

    ctx = build_context(assessment)
    intent = _classify(q.lower())
    topic = _topic_from_question(q.lower())
    simulation = False
    source = "rules"

    if intent == "constraint":
        payload = constraint_reply(assessment, q)
        text = payload.get("answer") or ""
        source = payload.get("source") or "rules"
        sections = payload.get("sections") or {}
        rec = payload.get("recommendation")
    elif intent == "whatif":
        from engine.whatif import simulate

        sim = simulate(q, assessment, topic=topic)
        simulation = True
        text = sim.get("operator_answer") or sim.get("narrative") or "I don't have enough live data to simulate that."
        if q.lower().startswith("should i"):
            band = risk_band((sim.get("risk") or {}).get("level"))
            if band in ("HIGH", "CRITICAL"):
                text = "Based on the current condition, I would not make that change.\n\n" + text
            elif band == "MEDIUM":
                text = "I would only make that change gradually, with monitoring.\n\n" + text
            else:
                text = "Based on the current condition, that change is currently acceptable if you monitor the response.\n\n" + text
        sections = {"CURRENT STATUS": "SIMULATION", "RISK": (sim.get("risk") or {}).get("level") or ""}
        rec = None
    else:
        rec = None
        handlers = {
            "done": lambda: _done(ctx),
            "handover": lambda: _handover(ctx),
            "summary": lambda: _summary(ctx),
            "how_is": lambda: _how_is(ctx),
            "whats_wrong": lambda: _whats_wrong(ctx),
            "why_not_high": lambda: _why_not_high(ctx),
            "why_risk": lambda: _why_risk(ctx),
            "why_happened": lambda: _why_happened(ctx),
            "alarm": lambda: _alarm(ctx),
            "why": lambda: _why(ctx),
            "history": lambda: _history(ctx),
            "after_change": lambda: _after_change(ctx),
            "what_changed": lambda: _what_changed(ctx),
            "when": lambda: _when(ctx),
            "worse": lambda: _worse(ctx, topic),
            "minutes_ago": lambda: _minutes_ago(ctx, q.lower()),
            "keep_running": lambda: _keep_running(ctx),
            "what_to_do": lambda: _what_to_do(ctx),
            "monitor": lambda: _monitor(ctx),
            "cause": lambda: _cause(ctx),
            "priority": lambda: _priority(ctx),
            "explain_param": lambda: _explain_param(ctx, q.lower()),
            "param": lambda: _param(ctx, q.lower()),
            "normal_range": lambda: _normal_range(ctx, q.lower()),
            "expected": lambda: _expected(ctx),
            "show_trend": lambda: _show_trend(ctx, q.lower()),
            "general": lambda: _general(ctx, q.lower()),
        }
        text = handlers.get(intent, lambda: _general(ctx, q.lower()))()
        hint = _next_prompt(intent, ctx)
        if hint:
            text = "{0}\n\n{1}".format(text, hint)
        sections = {
            "CURRENT STATUS": _status_word(ctx),
            "RISK": _status_word(ctx),
            "RECOMMENDED ACTION": (ctx.get("currentAssessment") or {}).get("action") or "",
        }
        if not simulation:
            text, source = _maybe_llm(q, text, ctx)

    memory.remember(intent, topic, q, text)
    event_log.emit(
        "OPERATOR_QUESTION",
        source="OPERATOR",
        severity=_status_word(ctx),
        context=q,
        message="Operator Question",
        operator_response=q[:180],
        aera_assessment=_status_word(ctx),
    )
    event_log.emit(
        "AERA_REPLY",
        source="AERA",
        severity=_status_word(ctx),
        context=text[:240],
        message="AERA Response",
        aera_assessment=text[:180],
        recommendation=((ctx.get("currentAssessment") or {}).get("action") or "")[:160],
        outcome="Logged",
    )
    try:
        from engine.pipeline import engine as live_engine

        if live_engine.latest:
            live_engine.latest["events"] = event_log.recent()
    except Exception:
        pass
    return {
        "answer": text,
        "source": source,
        "sections": sections,
        "simulation": simulation,
        "risk_level": (assessment.get("risk") or {}).get("level"),
        "intent": intent,
        "recommendation": rec or (ctx.get("recommendations") if intent == "constraint" else None),
        "confidence": 0.7 if (ctx.get("similar") or {}).get("count") else 0.5,
    }
