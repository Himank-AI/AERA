from __future__ import annotations

from engine.pipeline import SituationEngine
from knowledge.motor import expected_value


def _motor(temp, current, vib, speed, load, mode="RUNNING", status="NORMAL"):
    return {
        "code": "MOTOR-01",
        "name": "Motor 01",
        "operating_mode": mode,
        "status": status,
        "direction": "FWD",
        "drive_status": "RUN",
        "sensors": {
            "temperature": temp,
            "current": current,
            "vibration": vib,
            "speed": speed,
            "voltage": 232.0,
            "load": load,
            "power": 2.4,
            "torque": 15.0,
            "frequency": speed / 30.0,
            "runtime": 0.1,
        },
        "timestamp": "2026-09-10T10:00:00",
    }


def test_temperature_contextual_not_fixed_threshold():
    cool_load_expected = expected_value("temperature", 30.0, 1450.0, 0.1)
    hot_load_expected = expected_value("temperature", 85.0, 1450.0, 0.1)
    assert cool_load_expected < 62
    assert hot_load_expected > 62
    # 65°C is more unusual at 30% load than at 85% load.
    assert abs(65 - cool_load_expected) > abs(65 - hot_load_expected)


def test_normal_running_is_normal():
    engine = SituationEngine()
    engine.connected = True
    for _ in range(12):
        assessment = engine.evaluate(_motor(62.0, 10.2, 2.8, 1450.0, 64.0), {"scenario": "NORMAL"})
    assert assessment["connected"] is True
    assert assessment["risk"]["level"] in ("NORMAL", "MONITOR")
    assert assessment["sensors"]["temperature"] == 62.0


def test_developing_bearing_pattern_raises_risk():
    engine = SituationEngine()
    engine.history_events = [
        {
            "event_number": 1201,
            "machine": "MOTOR-01",
            "pattern_family": "motor_bearing_failure",
            "vibration": 7.4,
            "temperature": 80.5,
            "current": 14.5,
            "speed": 1406.0,
            "voltage": 231.5,
            "trend": {"vibration": 1, "temperature": 1, "current": 1, "speed": -1},
            "failure": True,
            "intervention": True,
            "operator_action": "Bearing replaced",
            "outcome": "Motor returned to normal",
            "description": "Bearing wear",
            "timestamp": "2026-08-12T10:00:00",
        }
    ] * 4
    temps = [55, 57, 60, 63, 66, 70, 74, 78]
    vibs = [2.0, 2.2, 2.5, 2.9, 3.4, 4.2, 5.1, 6.2]
    currents = [5.8, 6.0, 6.3, 6.6, 11.5, 12.4, 13.2, 14.0]
    speeds = [1450, 1446, 1438, 1428, 1418, 1410, 1404, 1396]
    last = None
    for temp, vib, current, speed in zip(temps, vibs, currents, speeds):
        last = engine.evaluate(_motor(temp, current, vib, speed, 78.0, status="ANOMALY"), {"scenario": "MOTOR_DEGRADATION"})
    assert last is not None
    assert last["risk"]["score"] >= 50
    assert last["situation"]["id"] in ("bearing_mechanical", "overload", "overheat")
    assert last["similar"]["count"] >= 1
    assert last["why_flagged"]["points"]


def test_does_not_invent_data_when_empty():
    engine = SituationEngine()
    assessment = engine.evaluate({}, {})
    assert assessment["connected"] is False
    assert assessment["sensors"] == {}
    assert "will not invent" in assessment["narrative"].lower() or "not connected" in assessment["error"].lower()
