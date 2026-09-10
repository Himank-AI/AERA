"""Shared real-time event log. Motor, HMI, and AERA all write here."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(stamp: Optional[str] = None) -> datetime:
    raw = stamp or _utcnow()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return datetime.now(timezone.utc)


KIND_BY_TYPE = {
    "MOTOR_STARTED": ("HMI Action", "Motor Started", "Recorded"),
    "MOTOR_STOPPED": ("HMI Action", "Motor Stopped", "Recorded"),
    "TEMPERATURE_CHANGED": ("Parameter Change", "Temperature Changed", "Recorded"),
    "VIBRATION_CHANGED": ("Parameter Change", "Vibration Changed", "Recorded"),
    "RPM_CHANGED": ("Parameter Change", "RPM Changed", "Recorded"),
    "CURRENT_CHANGED": ("Parameter Change", "Current Changed", "Recorded"),
    "VOLTAGE_CHANGED": ("Parameter Change", "Voltage Changed", "Recorded"),
    "LOAD_CHANGED": ("Parameter Change", "Load Changed", "Recorded"),
    "ALARM_TRIGGERED": ("Alarm", "Alarm Active", "Active"),
    "ALARM_RETURNED": ("Alarm", "Alarm Return", "Return"),
    "ALARM_CLEARED": ("Alarm", "Alarm Cleared", "Resolved"),
    "ANOMALY_DETECTED": ("AI Analysis", "AERA Detected Anomaly", "Recorded"),
    "AERA_ANALYSIS": ("AI Analysis", "AERA Analysis", "Recorded"),
    "RECOMMENDATION_ISSUED": ("Copilot Action", "Recommendation Issued", "Issued"),
    "RECOMMENDATION_ACCEPTED": ("Operator Interaction", "Recommendation Accepted", "Recorded"),
    "RECOMMENDATION_REJECTED": ("Operator Interaction", "Recommendation Rejected", "Recorded"),
    "ALTERNATIVE_ACTION_REQUESTED": ("Copilot Action", "Alternative Recommendation Issued", "Issued"),
    "OPERATOR_INTERVENTION": ("Operator Interaction", "Operator Intervention", "Recorded"),
    "FAULT_OCCURRED": ("Alarm", "Fault Occurred", "Active"),
    "FAULT_RESOLVED": ("Alarm", "Fault Resolved", "Resolved"),
    "CONDITION_IMPROVED": ("AI Analysis", "Condition Improved", "Recorded"),
    "OPERATOR_QUESTION": ("Operator Interaction", "Operator Question", "Recorded"),
    "AERA_REPLY": ("Copilot Action", "AERA Response", "Recorded"),
}


class EventLog:
    def __init__(self, limit: int = 400) -> None:
        self.limit = limit
        self.events: List[Dict[str, Any]] = []

    def emit(
        self,
        event_type: str,
        *,
        parameter: str = "",
        previous: Any = None,
        new: Any = None,
        severity: str = "NORMAL",
        source: str = "SYSTEM",
        context: str = "",
        unit: str = "",
        message: str = "",
        alarm_status: str = "",
        event_kind: str = "",
        condition: str = "",
        equipment: str = "MOTOR-01",
        aera_assessment: str = "",
        recommendation: str = "",
        operator_response: str = "",
        outcome: str = "",
    ) -> Dict[str, Any]:
        parsed = _parse()
        kind, default_message, default_status = KIND_BY_TYPE.get(event_type, ("Event", event_type.replace("_", " ").title(), "Recorded"))
        event = {
            "id": (self.events[-1]["id"] + 1) if self.events else 1,
            "timestamp": parsed.isoformat(),
            "date": parsed.strftime("%d/%m/%Y"),
            "clock": parsed.strftime("%H:%M:%S"),
            "event_type": event_type,
            "message": message or default_message,
            "alarm_status": alarm_status or default_status,
            "event_kind": event_kind or kind,
            "parameter": parameter,
            "previous": previous,
            "new": new,
            "unit": unit,
            "severity": severity,
            "source": source,
            "context": context,
            "condition": condition,
            "equipment": equipment,
            "aera_assessment": aera_assessment,
            "recommendation": recommendation,
            "operator_response": operator_response,
            "outcome": outcome,
        }
        self.events.append(event)
        if len(self.events) > self.limit:
            self.events = self.events[-self.limit :]
        return event

    def recent(self, n: int = 120) -> List[Dict[str, Any]]:
        return list(reversed(self.events[-n:]))

    def all(self) -> List[Dict[str, Any]]:
        return list(reversed(self.events))

    def reset(self) -> None:
        self.events = []


event_log = EventLog()
