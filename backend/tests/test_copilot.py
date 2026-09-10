from __future__ import annotations

from engine.copilot import answer, memory
from engine.events import event_log
from engine.pipeline import SituationEngine
from engine.recommend import rec_state
from engine.simulator import MotorSimulator
from knowledge.history_data import HISTORY_EVENTS, history_resolutions


def _prep():
    event_log.reset()
    rec_state.reset()
    memory.reset()
    engine = SituationEngine()
    sim = MotorSimulator()
    for _ in range(20):
        sim.step(0.25)
        engine.analytics.push(sim.as_motor()["sensors"], "")
    return engine, sim


def _eval(engine: SituationEngine, sim: MotorSimulator, n: int = 4):
    last = None
    for _ in range(n):
        sim.step(0.25)
        engine.ingest_backend(list(HISTORY_EVENTS), history_resolutions(), [], sim.alarms, True, "")
        last = engine.evaluate(sim.as_motor(), sim.as_telemetry())
    return last


def test_how_is_motor_uses_live_values():
    engine, sim = _prep()
    assessment = _eval(engine, sim, 2)
    reply = answer("How is the motor?", assessment)
    text = reply["answer"]
    assert "Temperature" in text
    assert str(int(assessment["sensors"]["temperature"]))[:2] in text or "{0:.1f}".format(assessment["sensors"]["temperature"]) in text
    assert "No active alarms" in text or "Active alarm" in text
    types = {row["event_type"] for row in event_log.events}
    assert "OPERATOR_QUESTION" in types
    assert "AERA_REPLY" in types


def test_keep_running_is_not_treated_as_constraint():
    engine, sim = _prep()
    assessment = _eval(engine, sim, 2)
    reply = answer("Can I keep the motor running?", assessment)
    assert "ALTERNATIVE ACTION" not in reply["answer"]
    assert "Yes" in reply["answer"] or "continue" in reply["answer"].lower()


def test_follow_up_why_uses_live_risk_context():
    engine, sim = _prep()
    sim.set_param("load", 50.0)
    sim.set_param("vibration", 7.5)
    assessment = _eval(engine, sim, 6)
    answer("What's wrong?", assessment)
    follow = answer("Why?", assessment)
    assert "7.5" in follow["answer"] or "Vibration" in follow["answer"] or "RISK" in follow["answer"]


def test_history_question_does_not_invent_counts():
    engine, sim = _prep()
    sim.set_param("vibration", 7.5)
    assessment = _eval(engine, sim, 6)
    reply = answer("Has this happened before?", assessment)
    count = int((assessment.get("similar") or {}).get("count") or 0)
    if count:
        assert str(count) in reply["answer"]
        assert str((assessment.get("similar") or {}).get("intervention_count")) in reply["answer"]
    else:
        assert "don't have a close historical match" in reply["answer"].lower() or "do not have" in reply["answer"].lower()


def test_cannot_reduce_load_gives_alternative():
    engine, sim = _prep()
    sim.set_param("vibration", 7.5)
    assessment = _eval(engine, sim, 6)
    rec_state.status = "pending"
    rec_state.primary = "Inspect bearing alignment and lubrication."
    rec_state.alternative = ["Reduce load to 60%.", "Monitor vibration continuously."]
    reply = answer("I can't reduce the load.", assessment)
    assert "ALTERNATIVE ACTION" in reply["answer"]
    after = reply["answer"].split("ALTERNATIVE ACTION", 1)[-1]
    assert "Reduce load to 60%" not in after
    assert "RISK remains" in reply["answer"] or "Risk remains" in reply["answer"]
    worse = answer("Is it getting worse?", assessment)
    assert "Vibration" in worse["answer"] or "vibration" in worse["answer"]
    assert "Load has increased" not in worse["answer"]


def test_why_risk_uses_live_vibration():
    engine, sim = _prep()
    sim.set_param("load", 52.0)
    sim.set_param("vibration", 7.2)
    assessment = _eval(engine, sim, 6)
    reply = answer("Why is the risk high?", assessment)
    assert "RISK is" in reply["answer"] or "because" in reply["answer"].lower()
    assert "Vibration" in reply["answer"]


def test_whatif_increase_load_does_not_move_motor():
    engine, sim = _prep()
    assessment = _eval(engine, sim, 2)
    before = dict(sim.values)
    reply = answer("What if I increase the load to 90%?", assessment)
    assert "WHAT-IF ANALYSIS" in reply["answer"]
    assert reply.get("simulation") is True
    assert abs(sim.values["load"] - before["load"]) < 0.05
    assert "simulation" in reply["answer"].lower() or "has not been changed" in reply["answer"].lower()


def test_whatif_temperature_uses_live_starting_point():
    engine, sim = _prep()
    assessment = _eval(engine, sim, 2)
    temp = assessment["sensors"]["temperature"]
    reply = answer("What if I increase the temperature?", assessment)
    assert "WHAT-IF ANALYSIS" in reply["answer"]
    assert "{0:.0f}".format(temp)[:2] in reply["answer"] or "{0:.1f}".format(temp) in reply["answer"]
    assert "load" not in reply["answer"].split("Requested")[-1][:40].lower() or "Temperature" in reply["answer"]
    engine, sim = _prep()
    assessment = _eval(engine, sim, 2)
    reply = answer("What is the current load?", assessment)
    assert "%" in reply["answer"]
    assert "A." not in reply["answer"] or "Load" in reply["answer"] or "load" in reply["answer"]
