"""Operator-facing recommendation and alternative-action layer.

Deterministic. Uses the situation engine output plus historical outcomes.
Never invents sensor values.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from engine.events import event_log
from knowledge.history_data import HISTORY_EVENTS, average_resolution_minutes

CONSTRAINT_TOKENS = (
    "can't",
    "cannot",
    "can not",
    "not possible",
    "unable",
    "can't stop",
    "cannot stop",
    "can't do",
    "cannot do",
    "what else",
    "alternative",
    "another option",
    "backup",
    "give me another",
    "i cannot",
    "i can't",
    "do not stop",
    "don't stop",
    "must keep running",
    "cannot shut",
    "can't reduce",
    "cannot reduce",
)


def _clock(stamp: Optional[str] = None) -> str:
    raw = stamp or datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%H:%M:%S")
    except ValueError:
        return raw[11:19] if len(raw) >= 19 else raw


def attention_label(level: Optional[str]) -> str:
    key = (level or "UNKNOWN").upper()
    return {
        "NORMAL": "NORMAL",
        "MONITOR": "ATTENTION",
        "LOW": "ATTENTION",
        "MEDIUM": "ATTENTION",
        "HIGH": "HIGH RISK",
        "CRITICAL": "CRITICAL",
        "UNKNOWN": "UNKNOWN",
        "ATTENTION": "ATTENTION",
        "HIGH RISK": "HIGH RISK",
    }.get(key, key)


def risk_band(level: Optional[str]) -> str:
    """Operator-facing risk: LOW / MEDIUM / HIGH / CRITICAL."""
    key = (level or "UNKNOWN").upper()
    return {
        "NORMAL": "LOW",
        "MONITOR": "LOW",
        "LOW": "LOW",
        "MEDIUM": "MEDIUM",
        "HIGH": "HIGH",
        "CRITICAL": "CRITICAL",
        "ATTENTION": "MEDIUM",
        "HIGH RISK": "HIGH",
        "UNKNOWN": "LOW",
        "RESOLVED": "LOW",
    }.get(key, "LOW")


def is_constraint(text: str) -> bool:
    q = (text or "").lower()
    return any(token in q for token in CONSTRAINT_TOKENS)


class RecommendationState:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.key = ""
        self.status = "idle"
        self.primary = ""
        self.alternative: List[str] = []
        self.detected_at = ""
        self.analyzed_at = ""
        self.recommended_at = ""
        self.rejected_reason = ""
        self.applied = False
        self.history_minutes = 0.0
        self._accept_alternative = False
        self.latched = "NORMAL"
        self.pending = "NORMAL"
        self.pending_ticks = 0
        self.hold_ticks = 0
        self.resolved_ticks = 0
        self.last_analysis_key = ""

    def latch(self, incoming: str) -> str:
        rank = {"NORMAL": 0, "RESOLVED": 0, "ATTENTION": 1, "HIGH RISK": 2, "CRITICAL": 3}
        shown = incoming if incoming in rank else "NORMAL"
        current = self.latched if self.latched in rank else "NORMAL"

        if rank[shown] > rank[current]:
            if shown == "ATTENTION":
                if self.pending == "ATTENTION":
                    self.pending_ticks += 1
                else:
                    self.pending = "ATTENTION"
                    self.pending_ticks = 1
                if self.pending_ticks < 2:
                    return current
            self.latched = shown
            self.pending = shown
            self.pending_ticks = 0
            self.hold_ticks = 0
            self.resolved_ticks = 0
            return shown

        if rank[shown] == rank[current]:
            self.hold_ticks = 0
            self.pending = shown
            if self.resolved_ticks > 0 and shown == "NORMAL":
                self.resolved_ticks -= 1
                return "RESOLVED"
            return current if current != "RESOLVED" else shown

        self.hold_ticks += 1
        if self.hold_ticks >= 6:
            previous = current
            self.latched = shown
            self.pending = shown
            self.pending_ticks = 0
            self.hold_ticks = 0
            if previous in ("HIGH RISK", "CRITICAL", "ATTENTION") and shown == "NORMAL":
                self.resolved_ticks = 4
                return "RESOLVED"
            return shown
        return current

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "primary": self.primary,
            "alternative": list(self.alternative),
            "detected_at": self.detected_at,
            "analyzed_at": self.analyzed_at,
            "recommended_at": self.recommended_at,
            "rejected_reason": self.rejected_reason,
            "applied": self.applied,
            "history_minutes": self.history_minutes,
            "actionable": self.status in ("pending", "rejected", "alternative") and bool(self.primary),
        }


rec_state = RecommendationState()


def _primary_and_alternative(assessment: Dict[str, Any]) -> Tuple[str, List[str]]:
    situation = assessment.get("situation") or {}
    similar = assessment.get("similar") or {}
    sid = situation.get("id") or "normal"
    matches = similar.get("matches") or []
    successful = [row.get("operator_action") for row in matches if row.get("operator_action") and row.get("intervention")]

    if sid == "bearing_mechanical":
        primary = "Inspect bearing alignment and lubrication."
        alternative = [
            "Reduce load to 60%.",
            "Monitor vibration continuously.",
            "Watch temperature trend for the next 2 minutes.",
            "Schedule bearing inspection at the next safe stop.",
        ]
        return primary, alternative
    if sid == "overload":
        return "Reduce load toward 60–70% and re-check current versus speed.", [
            "Hold current load only if production requires it.",
            "Watch current and temperature for 2 minutes.",
            "Inspect the driven equipment at the next opportunity.",
        ]
    if sid == "overheat":
        return "Check cooling path and reduce load.", [
            "Keep the motor running only if temperature is not still climbing.",
            "Confirm fan inlet is clear as soon as it is safe.",
            "Plan a stop if temperature continues rising.",
        ]
    if sid == "voltage_transient":
        return "Log the spike. No interruption required unless current or speed also moved.", [
            "Continue running.",
            "Confirm the spike duration on the next samples.",
        ]
    if sid == "high_load_thermal":
        return "Continue monitoring. Temperature is consistent with the current high load.", [
            "Keep watching vibration.",
            "Reduce load only if temperature keeps climbing.",
        ]
    if sid == "startup":
        return "Allow the start to settle. Do not treat inrush as a fault yet.", [
            "Abort the start if speed does not rise.",
        ]
    checks = (assessment.get("guidance") or {}).get("checks") or []
    if checks:
        return checks[0]["action"], [row["action"] for row in checks[1:3]]
    return "Continue normal operation.", []


def _likely_cause(assessment: Dict[str, Any]) -> str:
    sid = (assessment.get("situation") or {}).get("id")
    if sid == "bearing_mechanical":
        return "Bearing misalignment or lubrication issue."
    if sid == "overload":
        return "Mechanical overload on the driven equipment."
    if sid == "overheat":
        return "High load, cooling restriction, or developing friction."
    if sid == "voltage_transient":
        return "Incoming supply or drive bus spike."
    if sid == "high_load_thermal":
        return "Expected heating under high process load."
    if sid == "startup":
        return "Expected inrush while the motor is starting."
    return (assessment.get("situation") or {}).get("possible_cause") or "No abnormal cause identified."


def _history_line(assessment: Dict[str, Any]) -> str:
    similar = assessment.get("similar") or {}
    count = int(similar.get("count") or 0)
    if not count:
        return "No closely matching Motor 01 events in stored history."
    need = int(similar.get("intervention_count") or 0)
    fails = int(similar.get("failure_count") or 0)
    family = (assessment.get("situation") or {}).get("family") or ""
    minutes = average_resolution_minutes(family)
    bits = ["Similar condition detected {0} times previously.".format(count)]
    bits.append("{0} of {1} cases required operator intervention.".format(need, count))
    if fails:
        bits.append("{0} led to a trip or failure.".format(fails))
    if minutes:
        bits.append("Previous average resolution: {0:.0f} minutes.".format(minutes))
    return " ".join(bits)


def _recent_hmi_change(assessment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for row in assessment.get("events") or []:
        kind = str(row.get("event_type") or "")
        if kind.endswith("_CHANGED") and (row.get("source") or "") in ("HMI", "OPERATOR"):
            return row
    return None


def _what_line(assessment: Dict[str, Any]) -> str:
    deviations = assessment.get("deviations") or []
    notable = [row for row in deviations if row.get("unusual") or abs(row.get("percent_change") or 0) >= 8]
    change = _recent_hmi_change(assessment)
    rising = [row for row in deviations if (row.get("percent_change") or 0) > 6]
    if change and len(rising) >= 3:
        names = ", ".join((row.get("title") or row.get("name") or "") for row in rising[:4])
        return (
            "Several parameters changed together after {0}: {1}. "
            "This combination is more significant than any single change."
        ).format((change.get("parameter") or "a setpoint").replace("_", " "), names)
    if change and not notable:
        sensors = assessment.get("sensors") or {}
        return (
            "{0} changed from {1} to {2} {3}. Live temperature {4:.1f}°C, vibration {5:.1f} mm/s."
        ).format(
            (change.get("parameter") or "parameter").title(),
            change.get("previous"),
            change.get("new"),
            change.get("unit") or "",
            float(sensors.get("temperature") or 0),
            float(sensors.get("vibration") or 0),
        )
    if not notable:
        sensors = assessment.get("sensors") or {}
        mode = (assessment.get("motor") or {}).get("status") or "STOPPED"
        return "Motor is {0}. Temperature {1:.1f}°C, vibration {2:.1f} mm/s.".format(
            str(mode).lower(),
            float(sensors.get("temperature") or 0),
            float(sensors.get("vibration") or 0),
        )
    bits = []
    for row in notable[:3]:
        shown = "{0:.1f}".format(float(row["value"]))
        bits.append("{0} is {1} {2}.".format(row["title"], shown, row["unit"]))
    return " ".join(bits)


def _analysis_line(assessment: Dict[str, Any]) -> str:
    deviations = assessment.get("deviations") or []
    unusual = [row for row in deviations if row.get("unusual")]
    sid = (assessment.get("situation") or {}).get("id")
    change = _recent_hmi_change(assessment)
    sensors = assessment.get("sensors") or {}
    vib = float(sensors.get("vibration") or 0)
    if change and (change.get("parameter") or "") == "load" and vib >= 5.0:
        return "Increasing load while vibration is already elevated increases the current risk. I do not recommend increasing the load further."
    if sid == "bearing_mechanical":
        row = next((item for item in deviations if item.get("name") == "vibration"), None)
        if row:
            return "Vibration is significantly above the expected range at {0:.1f} {1}.".format(float(row.get("value") or 0), row.get("unit") or "mm/s")
    if sid == "high_load_thermal":
        return "Temperature is elevated but consistent with previous high-load operation."
    rapid = [row for row in deviations if abs(row.get("percent_change") or 0) >= 12]
    if rapid:
        top = max(rapid, key=lambda row: abs(row.get("percent_change") or 0))
        return "The {0} trend is more concerning than the absolute value. It moved {1:.0f}% on the live window.".format(
            (top.get("title") or top.get("name") or "parameter").lower(), abs(float(top.get("percent_change") or 0))
        )
    if not unusual:
        if change:
            return "The motor is responding as expected so far. Continue monitoring temperature and vibration."
        return "Parameters are consistent with the current load and speed."
    top = max(unusual, key=lambda row: abs(row.get("percent_change") or 0))
    if abs(top.get("percent_change") or 0) >= 5:
        return "{0} moved from a normal operating point to {1} {2}.".format(top["title"], top["value"], top["unit"])
    return top.get("note") or "Deviation is outside the expected band for this operating point."


def sync_recommendation(assessment: Dict[str, Any]) -> Dict[str, Any]:
    risk = assessment.get("risk") or {}
    situation = assessment.get("situation") or {}
    level = risk.get("level") or "NORMAL"
    key = "{0}:{1}".format(situation.get("id") or "normal", attention_label(level))
    clock = _clock(assessment.get("timestamp"))
    primary, alternative = _primary_and_alternative(assessment)
    label = attention_label(level)
    sid = situation.get("id") or "normal"
    quiet = sid in ("normal", "voltage_transient", "startup", "high_load_thermal", "machine_alarm")
    actionable = label in ("HIGH RISK", "CRITICAL") or (label == "ATTENTION" and not quiet)

    if key != rec_state.key:
        rec_state.key = key
        rec_state.primary = primary
        rec_state.alternative = alternative
        rec_state.rejected_reason = ""
        rec_state.applied = False
        rec_state.history_minutes = average_resolution_minutes(situation.get("family") or "")
        rec_state.detected_at = clock
        rec_state.analyzed_at = clock
        rec_state.recommended_at = clock
        rec_state.status = "pending" if actionable else "idle"
        rec_state._accept_alternative = False
        if key != rec_state.last_analysis_key:
            rec_state.last_analysis_key = key
            if sid not in ("normal", None, ""):
                event_log.emit(
                    "AERA_ANALYSIS",
                    severity=label,
                    source="AERA",
                    context=situation.get("title") or primary,
                    message="AERA Analysis",
                    aera_assessment=situation.get("what") or primary,
                    condition=situation.get("title") or "",
                )
            if actionable and label in ("HIGH RISK", "CRITICAL"):
                event_log.emit(
                    "ANOMALY_DETECTED",
                    severity=label,
                    source="AERA",
                    context=situation.get("title") or primary,
                    message="AERA Detected Anomaly",
                    aera_assessment=situation.get("what") or "",
                )
                event_log.emit(
                    "RECOMMENDATION_ISSUED",
                    severity=label,
                    source="AERA",
                    context=primary,
                    message="Recommendation Issued",
                    recommendation=primary,
                    aera_assessment=situation.get("what") or "",
                )
    else:
        rec_state.primary = rec_state.primary or primary
        rec_state.alternative = rec_state.alternative or alternative

    return rec_state.as_dict()


def respond(action: str, message: str = "") -> Dict[str, Any]:
    action = (action or "").lower()
    if action in ("reject", "not_possible", "not possible"):
        rec_state.status = "rejected"
        rec_state.rejected_reason = message or "Operator cannot perform the recommended action now."
        event_log.emit(
            "RECOMMENDATION_REJECTED",
            source="OPERATOR",
            severity="ATTENTION",
            context=rec_state.rejected_reason,
            message="Operator Rejected Recommendation",
            operator_response="Not Possible",
            recommendation=rec_state.primary,
            outcome="Alternative recommendation issued",
        )
        rec_state.status = "alternative"
        event_log.emit(
            "ALTERNATIVE_ACTION_REQUESTED",
            source="AERA",
            context="AERA issued a backup action.",
            severity="ATTENTION",
            message="Alternative Recommendation Issued",
            recommendation=" ".join(rec_state.alternative),
            operator_response="Not Possible",
            outcome="Backup action issued",
        )
        return rec_state.as_dict()
    if action in ("alternative", "show_alternative"):
        rec_state.status = "alternative"
        event_log.emit("ALTERNATIVE_ACTION_REQUESTED", source="OPERATOR", context=message or "Operator asked for another action.", severity="ATTENTION")
        return rec_state.as_dict()
    if action in ("accept", "apply"):
        accepting_alternative = rec_state.status in ("rejected", "alternative")
        rec_state.status = "accepted"
        rec_state.applied = True
        chosen = " ".join(rec_state.alternative) if accepting_alternative else rec_state.primary
        event_log.emit(
            "RECOMMENDATION_ACCEPTED",
            source="OPERATOR",
            context=chosen or message,
            severity="NORMAL",
            message="Recommendation Accepted",
            operator_response="Accepted",
            recommendation=chosen,
            outcome="Operator accepted action",
        )
        rec_state._accept_alternative = accepting_alternative
        return rec_state.as_dict()
    return rec_state.as_dict()


def apply_side_effect(action: str) -> Optional[str]:
    """Return a simulator command when the accepted action changes the machine."""
    if action not in ("accept", "apply"):
        return None
    if getattr(rec_state, "_accept_alternative", False):
        return "reduce_load"
    if "reduce load" in (rec_state.primary or "").lower():
        return "reduce_load"
    return None


def constraint_reply(assessment: Dict[str, Any], message: str) -> Dict[str, Any]:
    rec = respond("reject", message)
    alt = list(rec.get("alternative") or [])
    q = (message or "").lower()
    if any(token in q for token in ("reduce", "load")) and any(token in q for token in ("can't", "cannot", "not possible", "unable")):
        alt = [
            "Avoid increasing the load further.",
            "Monitor vibration and temperature closely.",
            "Schedule inspection at the next safe stop.",
        ]
    risk = attention_label((assessment.get("risk") or {}).get("level"))
    lines = ["Understood.", "", "ALTERNATIVE ACTION", "", "Since that action is not possible now:"]
    for index, step in enumerate(alt, start=1):
        lines.append("{0}. {1}".format(index, step))
    if not alt:
        lines.append("1. Continue operation only under close monitoring.")
        lines.append("2. Watch vibration and temperature continuously.")
        lines.append("3. Schedule inspection at the earliest safe opportunity.")
    lines.append("")
    lines.append("RISK remains {0}.".format(risk))
    text = "\n".join(lines)
    return {
        "answer": text,
        "source": "rules",
        "sections": {
            "CURRENT STATUS": risk,
            "RECOMMENDED ACTION": rec.get("primary") or "",
            "ALTERNATIVE ACTION": " ".join(alt),
            "RISK": risk,
        },
        "simulation": False,
        "risk_level": (assessment.get("risk") or {}).get("level"),
        "recommendation": rec,
    }


def build_copilot_view(assessment: Dict[str, Any]) -> Dict[str, Any]:
    rec = sync_recommendation(assessment)
    risk = assessment.get("risk") or {}
    situation = assessment.get("situation") or {}
    similar = assessment.get("similar") or {}
    label = attention_label(risk.get("level"))
    band = risk.get("band") or risk_band(risk.get("level"))
    sid = situation.get("id") or "normal"
    quiet_deviation = label == "ATTENTION" and sid in ("voltage_transient", "startup", "normal", "high_load_thermal", "machine_alarm")
    if sid == "normal" and label in ("NORMAL", "ATTENTION"):
        status_word = "NORMAL"
        what = "Motor operating within expected conditions."
        analysis = "No condition currently deserves operator interruption."
        history = "Routine deviations of this size have occurred without consequence."
        risk_why = "No historically significant failure pattern is active."
        action = "Continue normal operation."
        cause = ""
        alert = False
        band = "LOW"
    elif quiet_deviation:
        status_word = "ATTENTION"
        what = _what_line(assessment)
        if sid == "high_load_thermal":
            analysis = "Temperature is elevated but consistent with previous high-load operation. No immediate intervention required."
            band = "LOW" if band == "LOW" else band
        else:
            analysis = "This looks unusual at a glance, but history says it is usually harmless."
        history = _history_line(assessment)
        risk_why = "AERA is not treating this as a high-attention event."
        action = rec.get("primary") or "Continue monitoring."
        cause = _likely_cause(assessment)
        alert = False
    else:
        status_word = label
        what = _what_line(assessment)
        analysis = _analysis_line(assessment)
        history = _history_line(assessment)
        risk_why = risk.get("potential_consequence") or situation.get("consequence") or "Condition may worsen if ignored."
        action = rec.get("primary") or risk.get("recommended_response")
        cause = _likely_cause(assessment)
        alert = label in ("HIGH RISK", "CRITICAL")

    status_word = rec_state.latch(status_word)
    if status_word == "RESOLVED":
        alert = False
        band = "LOW"
        what = "Condition has returned to the expected range."
        analysis = "AERA is no longer interrupting the operator."
        action = "Continue normal operation."
    elif status_word == "NORMAL":
        alert = False
        band = "LOW"

    risk_body = "RISK: {0}\n\n{1}".format(band, risk_why)

    successful = ""
    matches = similar.get("matches") or []
    if matches:
        successful = (matches[0].get("operator_action") or matches[0].get("solution") or "") if matches else ""

    return {
        "status": status_word,
        "what": what,
        "analysis": analysis,
        "history": history,
        "risk": risk_body,
        "risk_band": band,
        "cause": cause,
        "cause_certainty": "LIKELY CAUSE" if sid in ("bearing_mechanical", "overload") else "POSSIBLE CAUSE",
        "action": action,
        "alert": alert or status_word in ("HIGH RISK", "CRITICAL"),
        "alternative": rec.get("alternative") or [],
        "successful_action": successful,
        "similar_count": int(similar.get("count") or 0),
        "intervention_count": int(similar.get("intervention_count") or 0),
        "failure_count": int(similar.get("failure_count") or 0),
        "history_minutes": rec.get("history_minutes") or 0,
        "timings": {
            "detected": rec.get("detected_at"),
            "analyzed": rec.get("analyzed_at"),
            "recommendation": rec.get("recommended_at"),
        },
        "recommendation": rec,
    }
