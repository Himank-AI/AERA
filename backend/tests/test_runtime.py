from __future__ import annotations

from engine.events import event_log
from engine.pipeline import SituationEngine
from engine.recommend import rec_state, respond
from engine.simulator import MotorSimulator
from knowledge.history_data import HISTORY_EVENTS, history_resolutions


def _eval_sim(engine: SituationEngine, sim: MotorSimulator, n: int = 1):
    last = None
    for _ in range(n):
        sim.step(0.25)
        engine.ingest_backend(list(HISTORY_EVENTS), history_resolutions(), [], sim.alarms, True, "")
        last = engine.evaluate(sim.as_motor(), sim.as_telemetry())
    return last


def setup_function() -> None:
    event_log.reset()
    rec_state.reset()


def test_start_stop_share_state():
    sim = MotorSimulator()
    sim.stop()
    sim.step(3.0)
    assert sim.mode in ("STOPPING", "STOPPED")
    sim.start()
    assert sim.mode == "STARTING"
    for _ in range(20):
        sim.step(0.25)
    assert sim.mode == "RUNNING"
    assert sim.values["speed"] > 800


def test_hmi_parameter_reaches_engine():
    engine = SituationEngine()
    sim = MotorSimulator()
    for _ in range(20):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    sim.set_param("vibration", 7.2, source="HMI")
    assessment = _eval_sim(engine, sim, 6)
    assert assessment["sensors"]["vibration"] >= 6.5
    assert assessment["connected"] is True
    assert assessment["attention"] in ("ATTENTION", "HIGH RISK", "CRITICAL")
    assert assessment["similar"]["count"] >= 1


def test_reject_yields_alternative_and_logs():
    engine = SituationEngine()
    engine.history_events = list(HISTORY_EVENTS)
    sim = MotorSimulator()
    for _ in range(20):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    sim.set_param("vibration", 7.2, source="HMI")
    _eval_sim(engine, sim, 8)
    rec_state.status = "pending"
    rec_state.primary = "Inspect bearing alignment and lubrication."
    rec_state.alternative = ["Reduce load to 60%.", "Monitor vibration continuously."]
    rec = respond("reject", "I cannot stop the motor.")
    assert rec["status"] == "alternative"
    assert rec["alternative"]
    events = engine.latest.get("events") if engine.latest else []
    types = {row["event_type"] for row in (events or [])}
    # recommendation events are on the global event log, pulled into the next evaluate
    assessment = _eval_sim(engine, sim, 1)
    types = {row["event_type"] for row in assessment["events"]}
    assert "RECOMMENDATION_REJECTED" in types
    assert "ALTERNATIVE_ACTION_REQUESTED" in types


def test_history_is_preloaded():
    assert len(HISTORY_EVENTS) >= 8
    bearing = [row for row in HISTORY_EVENTS if row["pattern_family"] == "motor_bearing_failure"]
    assert len(bearing) == 8
    assert sum(1 for row in bearing if row["intervention"]) == 6
    thermal = [row for row in HISTORY_EVENTS if row["pattern_family"] == "temp_high_load"]
    assert len(thermal) >= 4
    assert all(not row["intervention"] for row in thermal)


def test_operator_set_temperature_is_immediate():
    engine = SituationEngine()
    sim = MotorSimulator()
    for _ in range(12):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    sim.set_param("temperature", 82.0, source="HMI")
    engine.ingest_backend(list(HISTORY_EVENTS), history_resolutions(), [], sim.alarms, True, "")
    assessment = engine.evaluate(sim.as_motor(), sim.as_telemetry())
    assert abs(assessment["sensors"]["temperature"] - 82.0) < 0.2
    assert abs(sim.values["temperature"] - 82.0) < 0.05


def test_high_load_heating_is_attention_not_high_risk():
    engine = SituationEngine()
    sim = MotorSimulator()
    for _ in range(24):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    sim.set_param("load", 90.0, source="HMI")
    sim.set_param("temperature", 85.0, source="HMI")
    assessment = _eval_sim(engine, sim, 8)
    assert abs(assessment["sensors"]["temperature"] - 85.0) < 0.2
    assert assessment["sensors"]["load"] >= 88
    assert assessment["sensors"]["vibration"] < 4.2
    assert assessment["attention"] in ("NORMAL", "ATTENTION")
    assert assessment["attention"] not in ("HIGH RISK", "CRITICAL")
    assert (assessment.get("risk") or {}).get("band") in ("LOW", "MEDIUM")
    assert "RISK: LOW" in (assessment["copilot_view"].get("risk") or "") or (assessment.get("risk") or {}).get("band") == "LOW"
    assert assessment["situation"]["id"] == "high_load_thermal"
    assert not assessment["copilot_view"].get("alert")


def test_high_vibration_at_moderate_load_is_alert_high_risk():
    engine = SituationEngine()
    sim = MotorSimulator()
    for _ in range(24):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    sim.set_param("load", 50.0, source="HMI")
    sim.set_param("vibration", 7.5, source="HMI")
    assessment = _eval_sim(engine, sim, 6)
    assert assessment["sensors"]["vibration"] >= 7.0
    assert assessment["sensors"]["load"] <= 55
    assert assessment["attention"] in ("HIGH RISK", "CRITICAL")
    assert assessment["copilot_view"].get("alert") is True
    assert (assessment.get("risk") or {}).get("band") in ("HIGH", "CRITICAL")
    assert "RISK: HIGH" in (assessment["copilot_view"].get("risk") or "") or "RISK: CRITICAL" in (assessment["copilot_view"].get("risk") or "")
    assert sim.health_status == "ALARM"
    assert any(row.get("title") == "HIGH VIBRATION" for row in sim.alarms)


def test_alarm_active_then_return():
    sim = MotorSimulator()
    sim.set_param("vibration", 7.5, source="HMI")
    assert any(row.get("alarm_status") == "Active" for row in sim.alarms)
    types = [row["event_type"] for row in event_log.events]
    assert "ALARM_TRIGGERED" in types
    sim.set_param("vibration", 2.2, source="HMI")
    assert sim.alarms == []
    types = [row["event_type"] for row in event_log.events]
    assert "ALARM_RETURNED" in types


def test_status_does_not_flicker_on_held_override():
    engine = SituationEngine()
    sim = MotorSimulator()
    for _ in range(16):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    sim.set_param("temperature", 80.5, source="HMI")
    labels = []
    for _ in range(10):
        assessment = _eval_sim(engine, sim, 1)
        labels.append(assessment["copilot_view"]["status"])
    flips = sum(1 for index in range(1, len(labels)) if labels[index] != labels[index - 1])
    assert flips <= 2
    assert abs(sim.values["temperature"] - 80.5) < 0.05


def test_status_holds_while_abnormal_persists():
    engine = SituationEngine()
    sim = MotorSimulator()
    for _ in range(20):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    sim.set_param("load", 50.0, source="HMI")
    sim.set_param("vibration", 7.5, source="HMI")
    labels = []
    for _ in range(12):
        assessment = _eval_sim(engine, sim, 1)
        labels.append(assessment["copilot_view"]["status"])
    assert "RESOLVED" not in labels
    assert labels[-1] in ("HIGH RISK", "CRITICAL")
    assert assessment["copilot_view"].get("alert") is True
    assert assessment["similar"]["count"] >= 1
