"""Plant-specific expert notes. Distinct from generic generated advice."""
from __future__ import annotations

from typing import Any, Dict, List

EXPERT_CASES: List[Dict[str, Any]] = [
    {
        "id": "EXP-BRG-01",
        "problem": "Drive-end bearing wear",
        "symptoms": ["vibration rising", "current rising", "temperature rising", "speed dropping"],
        "pattern_family": "motor_bearing_failure",
        "cause": "Drive-end bearing wear on Motor 01",
        "diagnostic_process": [
            "Confirm load has not jumped independently of vibration.",
            "Listen for growl at the drive-end bearing.",
            "Inspect coupling for extra mechanical resistance.",
            "Isolate and inspect the bearing if vibration continues to climb.",
        ],
        "solution": "Motor stopped per SOP. Drive-end bearing inspected and replaced. Grease renewed. Motor restored.",
        "warnings": [
            "Do not keep the motor running if vibration exceeds 8 mm/s.",
            "Do not restart after a thermal trip without a mechanical check.",
        ],
        "outcome": "Vibration returned to the normal band. Motor returned to normal.",
        "notes": "This motor has a known history of drive-end bearing wear under sustained high load.",
        "source": "Morgan Chen, Engineer",
        "source_type": "expert",
        "verified": True,
    },
    {
        "id": "EXP-OVL-01",
        "problem": "Temporary high mechanical load",
        "symptoms": ["current rising", "speed dropping", "temperature rising slowly"],
        "pattern_family": "motor_overload",
        "cause": "Temporary high load on the connected equipment, not a bearing fault",
        "diagnostic_process": [
            "Check whether process demand actually increased.",
            "If vibration is stable, treat as load first, not bearing.",
            "Reduce process load if production allows.",
        ],
        "solution": "Operator reduced process load. Current and speed returned to the normal band without a stop.",
        "warnings": ["If vibration also rises, do not treat it as load-only."],
        "outcome": "No failure. Monitoring continued.",
        "notes": "One of the similar historical cases was harmless high load.",
        "source": "Jordan Hale, Experienced operator",
        "source_type": "expert",
        "verified": True,
    },
    {
        "id": "EXP-VLT-01",
        "problem": "Harmless incoming voltage spike",
        "symptoms": ["short voltage spike", "other parameters unchanged"],
        "pattern_family": "voltage_spike",
        "cause": "Temporary incoming supply spike that self-cleared",
        "diagnostic_process": [
            "Check duration. If it is 1–4 seconds and voltage returns, do not interrupt the operator.",
            "Confirm current, speed, and vibration did not follow the spike.",
        ],
        "solution": "No intervention. Event logged.",
        "warnings": ["A sustained voltage deviation with current change is not this case."],
        "outcome": "No significant impact. This pattern has occurred many times on Motor 01 without a fault.",
        "source": "Sam Okonkwo, Operator",
        "source_type": "expert",
        "verified": True,
    },
    {
        "id": "EXP-CPL-01",
        "problem": "Coupling mechanical resistance",
        "symptoms": ["current rising", "speed dropping", "vibration slightly up"],
        "pattern_family": "motor_overload",
        "cause": "Excessive mechanical resistance at the coupling",
        "diagnostic_process": [
            "Inspect the coupling before opening the bearing housing.",
            "Check for debris or misalignment.",
        ],
        "solution": "An experienced operator previously resolved a similar condition by inspecting the coupling and removing excessive mechanical resistance.",
        "warnings": ["Lock out before approaching the coupling."],
        "outcome": "Motor returned to normal without a bearing replacement.",
        "source": "Jordan Hale, Experienced operator",
        "source_type": "expert",
        "verified": True,
    },
]


SOPS: List[Dict[str, Any]] = [
    {
        "code": "SOP-MTR-BRG-01",
        "title": "Motor Bearing Inspection SOP",
        "purpose": "Diagnose elevated motor vibration with correlated temperature and current rise before a trip occurs.",
        "safety": [
            "Confirm the machine is in a safe operating mode before approaching.",
            "Wear hearing protection and gloves at the motor skid.",
            "Do not remove guards while the motor is running.",
            "If vibration exceeds 10 mm/s, keep personnel clear and escalate.",
        ],
        "steps": [
            "Identify Motor 01 and confirm the tag.",
            "Compare live vibration, temperature, current, and speed against the RUNNING baseline.",
            "Listen for growl or rumble at the drive-end bearing.",
            "Check coupling alignment and mounting bolt tightness after isolation if required.",
            "Inspect grease condition and bearing temperature after isolation.",
            "Record findings and recommend repair or continued monitoring.",
        ],
        "escalation": [
            "Escalate to maintenance if vibration remains above 6 mm/s for more than 10 minutes.",
            "Escalate immediately if speed drops while current and temperature continue to rise.",
            "If a trip occurs, isolate, lock out, and do not restart without a mechanical inspection.",
        ],
    },
    {
        "code": "SOP-MTR-TMP-01",
        "title": "Motor Overtemperature SOP",
        "purpose": "Respond to motor temperature rise above the warning band for the current load.",
        "safety": [
            "Treat the motor frame as a hot surface.",
            "Do not spray water on an energized motor.",
        ],
        "steps": [
            "Confirm temperature trend and duration.",
            "Check cooling fan, filters, and ambient conditions.",
            "Compare current against expected load. Overcurrent with heat indicates overload.",
            "Reduce process load if permitted.",
            "If temperature exceeds the critical band, request a controlled stop from supervision.",
        ],
        "escalation": [
            "Escalate if temperature remains well above the expected value for the current load.",
            "Call electrical maintenance if cooling is intact and current is normal.",
        ],
    },
    {
        "code": "SOP-MTR-OVL-01",
        "title": "Motor Overload SOP",
        "purpose": "Respond when current rises while speed falls, indicating extra mechanical demand.",
        "safety": ["Do not stand in line with couplings.", "Do not override drive current limits."],
        "steps": [
            "Check mechanical load first because current increased while speed decreased.",
            "Inspect the coupling and driven equipment.",
            "If vibration is also rising, follow the bearing SOP rather than load-only actions.",
            "If load cannot be reduced and temperature is climbing, stop according to plant procedure.",
        ],
        "escalation": [
            "Escalate to maintenance if current stays high after load is confirmed normal.",
            "Escalate immediately if a trip is approaching.",
        ],
    },
    {
        "code": "SOP-MTR-VLT-01",
        "title": "Motor Voltage Transient SOP",
        "purpose": "Decide whether a voltage spike needs action or only logging.",
        "safety": ["Do not open drive cubicles unless qualified."],
        "steps": [
            "Confirm whether voltage has returned to the normal band.",
            "Check current, speed, and vibration. If they did not move, treat as a supply transient.",
            "Check Motor 02 on the same supply if the spike persists.",
        ],
        "escalation": ["Escalate to electrical if voltage remains outside band for more than 10 seconds."],
    },
    {
        "code": "SOP-MTR-STR-01",
        "title": "Motor Startup SOP",
        "purpose": "Start Motor 01 so startup transients are not treated as failures.",
        "safety": ["Confirm guards are closed.", "Abort the start if any e-stop is active."],
        "steps": [
            "Verify permissives.",
            "Start and allow up to 20 seconds for current and vibration to settle.",
            "If the motor does not reach speed, abort and inspect.",
        ],
        "escalation": ["If the motor does not reach speed within 10 seconds, abort and inspect."],
    },
    {
        "code": "SOP-MTR-SAFE-01",
        "title": "Motor Safety and Escalation",
        "purpose": "AERA is an assistance system. Critical actions follow plant safety procedure.",
        "safety": [
            "AERA must never be treated as a guaranteed diagnosis.",
            "AERA does not start, stop, or reset the motor.",
            "Follow lockout/tagout before mechanical work.",
        ],
        "steps": [
            "For CRITICAL conditions, follow the plant SOP and escalate to a qualified person.",
            "Record the actual cause and outcome after the event.",
        ],
        "escalation": ["Call maintenance/engineer for HIGH or CRITICAL conditions that are not clearly load-related and recovering."],
    },
]


def sop_by_code(code: str) -> Dict[str, Any] | None:
    for row in SOPS:
        if row["code"] == code:
            return row
    return None


def matching_expert_cases(family: str, signals: List[str]) -> List[Dict[str, Any]]:
    hits = []
    for case in EXPERT_CASES:
        if family and case.get("pattern_family") == family:
            hits.append(case)
            continue
        joined = " ".join(case.get("symptoms") or []).lower()
        if any(token.lower() in joined for token in signals if token):
            hits.append(case)
    return hits
