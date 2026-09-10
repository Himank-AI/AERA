from __future__ import annotations

from engine.pipeline import engine
from engine.whatif import estimate
from knowledge.motor import expected_value


def healthy(load=64.0, **extra):
    sensors = {
        "temperature": expected_value("temperature", load, 1450.0, 0.2),
        "current": 10.2 * (load / 64.0),
        "vibration": 2.8,
        "speed": 1450.0 - 0.35 * max(0.0, load - 64.0),
        "voltage": 232.0,
        "load": load,
        "power": 232.0 * (10.2 * load / 64.0) * 0.001 * 0.92,
        "torque": 15.5 * (load / 64.0),
        "frequency": 48.3,
        "runtime": 0.4,
        "speed_setpoint": 1450.0,
    }
    sensors.update(extra)
    return {
        "connected": True,
        "health": 92,
        "motor": {"code": "MOTOR-01", "status": "NORMAL", "operating_mode": "RUNNING", "drive_status": "RUN"},
        "sensors": sensors,
        "situation": {"id": "normal", "family": ""},
        "risk": {"score": 12, "level": "NORMAL"},
    }


def degraded():
    return {
        "connected": True,
        "health": 48,
        "motor": {"code": "MOTOR-01", "status": "ANOMALY", "operating_mode": "RUNNING", "drive_status": "RUN"},
        "sensors": {
            "temperature": 78.0,
            "current": 14.2,
            "vibration": 6.4,
            "speed": 1408.0,
            "voltage": 231.0,
            "load": 88.0,
            "power": 3.0,
            "torque": 20.0,
            "frequency": 46.9,
            "runtime": 1.2,
            "speed_setpoint": 1450.0,
        },
        "situation": {"id": "bearing_mechanical", "family": "motor_bearing_failure"},
        "risk": {"score": 72, "level": "HIGH"},
    }


def test_same_input_same_output():
    a = healthy(60)
    first = estimate(a, {"load": 80, "duration_min": 15, "cooling": 1.0, "voltage": 232, "speed": 1450})
    second = estimate(a, {"load": 80, "duration_min": 15, "cooling": 1.0, "voltage": 232, "speed": 1450})
    assert first["predicted"] == second["predicted"]
    assert first["risk"]["score"] == second["risk"]["score"]
    assert first["command_sent"] is False


def test_load_ladder_increases_current_power_and_risk():
    a = healthy(40)
    scores = []
    currents = []
    for load in (20, 40, 60, 80, 90, 100):
        row = estimate(a, {"load": load, "duration_min": 15, "voltage": 232, "speed": 1450, "cooling": 1.0})
        scores.append(row["risk"]["score"])
        currents.append(row["predicted"]["current"])
    assert currents[0] < currents[2] < currents[4]
    assert scores[0] < scores[3] < scores[5]
    assert row["risk"]["level"] in ("MEDIUM", "HIGH", "CRITICAL")
    low = estimate(a, {"load": 20, "duration_min": 15, "voltage": 232, "speed": 1450, "cooling": 1.0})
    assert low["risk"]["level"] in ("LOW", "MONITOR")
    assert low["predicted"]["current"] < 8


def test_temperature_has_thermal_inertia():
    a = healthy(60)
    t5 = estimate(a, {"load": 90, "duration_min": 5, "voltage": 232, "speed": 1450, "cooling": 1.0})
    t60 = estimate(a, {"load": 90, "duration_min": 60, "voltage": 232, "speed": 1450, "cooling": 1.0})
    assert t5["predicted"]["temperature"] < t60["predicted"]["temperature"]
    assert t60["risk"]["score"] >= t5["risk"]["score"]


def test_reducing_load_restores_margin():
    a = healthy(90, temperature=82.0, current=14.0, vibration=4.2)
    high = estimate(a, {"load": 90, "duration_min": 30, "voltage": 232, "speed": 1450, "cooling": 1.0})
    low = estimate(a, {"load": 50, "duration_min": 30, "voltage": 232, "speed": 1450, "cooling": 1.0})
    assert low["predicted"]["current"] < high["predicted"]["current"]
    assert low["predicted"]["power"] < high["predicted"]["power"]
    assert low["margins"]["power"]["margin"] > high["margins"]["power"]["margin"]
    assert low["risk"]["score"] < high["risk"]["score"]


def test_low_voltage_high_load_raises_electrical_risk():
    a = healthy(64)
    normal = estimate(a, {"load": 90, "voltage": 232, "duration_min": 15, "speed": 1450, "cooling": 1.0})
    weak = estimate(a, {"load": 90, "voltage": 188, "duration_min": 15, "speed": 1450, "cooling": 1.0})
    assert weak["predicted"]["current"] > normal["predicted"]["current"]
    assert weak["margins"]["power"]["margin"] < normal["margins"]["power"]["margin"]
    assert weak["risk"]["score"] > normal["risk"]["score"]
    assert weak["risk"]["level"] in ("HIGH", "CRITICAL")


def test_cooling_failure_raises_temperature():
    a = healthy(75)
    ok = estimate(a, {"load": 80, "cooling": 1.0, "duration_min": 30, "voltage": 232, "speed": 1450})
    fail = estimate(a, {"load": 80, "cooling": 0.35, "duration_min": 30, "voltage": 232, "speed": 1450})
    assert fail["predicted"]["temperature"] > ok["predicted"]["temperature"]
    assert fail["risk"]["score"] > ok["risk"]["score"]


def test_bearing_plus_high_load_is_worse_than_healthy():
    h = estimate(healthy(90), {"load": 90, "duration_min": 20, "voltage": 232, "speed": 1450, "cooling": 1.0})
    d = estimate(degraded(), {"load": 90, "duration_min": 20, "voltage": 231, "speed": 1450, "cooling": 1.0})
    assert d["predicted"]["vibration"] > h["predicted"]["vibration"]
    assert d["risk"]["score"] > h["risk"]["score"]
    assert d["risk"]["level"] in ("HIGH", "CRITICAL")


def test_abrupt_change_adds_stress_versus_same_load():
    a = healthy(50)
    gradual = estimate(a, {"load": 55, "duration_min": 15, "voltage": 232, "speed": 1450, "cooling": 1.0, "abrupt": False})
    sudden = estimate(a, {"load": 90, "duration_min": 15, "voltage": 232, "speed": 1450, "cooling": 1.0, "abrupt": True})
    assert sudden["risk"]["factors"]["abrupt_penalty"] > gradual["risk"]["factors"]["abrupt_penalty"]
    assert sudden["risk"]["score"] > gradual["risk"]["score"]


def test_stopped_motor_does_not_pretend_to_rotate():
    a = healthy(70)
    stopped = estimate(a, {"stopped": True, "speed": 1450, "duration_min": 10})
    assert stopped["predicted"]["speed"] == 0
    assert stopped["predicted"]["current"] < 1
    assert stopped["command_sent"] is False


def test_temperature_question_does_not_raise_load():
    from engine.whatif import hypothesis_from_question

    sensors = healthy(50)["sensors"]
    hypo = hypothesis_from_question("What if I increase the temperature?", sensors)
    assert hypo.get("focus") == "temperature"
    assert abs(float(hypo.get("load") or 50) - 50) < 0.01
    row = estimate(healthy(50), question="What if I increase the temperature?")
    assert row["command_sent"] is False
    assert row["predicted"]["temperature"] > row["current"]["temperature"]
    assert "WHAT-IF ANALYSIS" in (row.get("operator_answer") or "")


def test_vibration_whatif_to_8_is_high_risk():
    row = estimate(healthy(55, vibration=2.5), question="What if vibration increases to 8 mm/s?")
    assert row["command_sent"] is False
    assert row["predicted"]["vibration"] >= 7.5
    assert row["risk"]["level"] in ("HIGH", "CRITICAL")
    assert abs(row["current"]["vibration"] - 2.5) < 0.2


def test_load_to_90_from_healthy_is_not_critical():
    row = estimate(healthy(55), question="What if I increase the load to 90%?")
    assert row["command_sent"] is False
    assert abs(row["predicted"]["load"] - 90) < 0.2
    assert row["predicted"]["current"] > row["current"]["current"]
    assert row["risk"]["level"] in ("LOW", "MONITOR", "MEDIUM", "HIGH")


def test_stop_whatif_does_not_spin():
    row = estimate(healthy(70), question="What happens if I stop the motor?")
    assert row["predicted"]["speed"] == 0
    assert row["command_sent"] is False
    assert "stop" in (row.get("operator_answer") or "").lower()
    row = estimate({"connected": False, "sensors": {}}, {"load": 90})
    assert "will not invent" in (row.get("error") or "").lower() or "not invent" in row["narrative"].lower()


def test_history_match_uses_engine_events_not_invention():
    previous = list(engine.history_events)
    engine.history_events = [
        {
            "event_number": 24,
            "machine": "MOTOR-01",
            "pattern_family": "motor_bearing_failure",
            "vibration": 6.8,
            "temperature": 80.0,
            "current": 14.0,
            "speed": 1406.0,
            "voltage": 231.0,
            "trend": {"vibration": 1, "temperature": 1, "current": 1, "speed": -1},
            "failure": True,
            "intervention": True,
            "operator_action": "Bearing inspected",
            "outcome": "No major failure",
            "description": "Bearing degradation",
            "timestamp": "2026-08-12T10:00:00",
        }
    ] * 3
    try:
        row = estimate(degraded(), {"load": 92, "duration_min": 20, "voltage": 231, "speed": 1450, "cooling": 1.0})
        assert row["history"]["count"] >= 1
        assert "bearing" in (row["history"]["summary"] or "").lower() or row["history"]["matches"]
    finally:
        engine.history_events = previous
