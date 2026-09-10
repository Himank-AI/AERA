"""MOTOR-01 calculation layer shared by live interpretation and What-If.

Relationships follow the PlantIQ Motor 01 physics in plantiq/backend/simulator/physics.py:
electrical power ≈ V × I × 0.001 × 0.92
torque ≈ 9550 × kW / RPM
frequency ≈ speed / 30
bearing drag raises current, temperature, vibration and drops speed
temperature is first-order (thermal inertia), not an instant jump.

This is a simplified industrial model for an HMI prototype, not a FEM motor study.
It is deterministic: the same inputs always produce the same outputs.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

# PlantIQ MOTOR-01 nominal running point (physics.py reset values).
NOMINAL_LOAD = 64.0
NOMINAL_CURRENT = 10.2
NOMINAL_TEMP = 62.0
NOMINAL_VIB = 2.8
NOMINAL_SPEED = 1450.0
NOMINAL_VOLTAGE = 232.0
POWER_COEFF = 0.92  # PlantIQ: P_kW = V * I * 0.001 * 0.92
POLES_FREQ_RATIO = 30.0  # 4-pole: f ≈ n / 30
AMBIENT = 28.0
TAU_MINUTES = 18.0  # thermal time constant at normal cooling
I_RATED = 15.9  # 10.2 A at 64% load → ~100% current
P_RATED = NOMINAL_VOLTAGE * I_RATED * 0.001 * POWER_COEFF  # ~3.39 kW
T_WARN = 78.0
T_CRIT = 88.0
VIB_WARN = 6.0
VIB_CRIT = 8.0
I_SAFE = 15.9


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def electrical_power_kw(voltage: float, current: float) -> float:
    """Same electrical power identity used by the Motor + HMI simulator."""
    return max(0.0, voltage * current * 0.001 * POWER_COEFF)


def torque_nm(power_kw: float, speed_rpm: float) -> float:
    return (power_kw * 9550.0) / max(speed_rpm, 1.0)


def mechanical_power_kw(torque: float, speed_rpm: float) -> float:
    omega = 2.0 * math.pi * max(speed_rpm, 0.0) / 60.0
    return (torque * omega) / 1000.0


def frequency_hz(speed_rpm: float) -> float:
    return speed_rpm / POLES_FREQ_RATIO


def speed_from_frequency(freq: float) -> float:
    return freq * POLES_FREQ_RATIO


def infer_bearing(sensors: Dict[str, float], situation: Optional[Dict[str, Any]] = None) -> float:
    """Invert PlantIQ vibration = 2.8 + 5.3 * bearing."""
    vib = float(sensors.get("vibration") or NOMINAL_VIB)
    situation = situation or {}
    family = (situation.get("family") or situation.get("id") or "").lower()
    if "bearing" in family:
        return clamp((vib - NOMINAL_VIB) / 5.3, 0.15, 1.0)
    return clamp((vib - NOMINAL_VIB) / 5.3, 0.0, 1.0)


def infer_overheat(sensors: Dict[str, float], situation: Optional[Dict[str, Any]] = None) -> float:
    temp = float(sensors.get("temperature") or NOMINAL_TEMP)
    load = float(sensors.get("load") or NOMINAL_LOAD)
    expected = 48.0 + 0.22 * load
    extra = (temp - expected) / 18.0
    situation = situation or {}
    if (situation.get("id") or "") == "overheat":
        return clamp(extra, 0.2, 1.0)
    return clamp(extra, 0.0, 1.0)


def infer_mode(motor: Dict[str, Any], sensors: Dict[str, float]) -> str:
    mode = str(motor.get("operating_mode") or motor.get("status") or "").upper()
    drive = str(motor.get("drive_status") or "").upper()
    speed = float(sensors.get("speed") or 0.0)
    if mode in ("STOPPED", "STOP", "OFF") or drive in ("STOP", "OFF"):
        return "STOPPED"
    if speed < 40 and mode not in ("RUNNING", "RUN"):
        return "STOPPED"
    if mode in ("STARTING", "START"):
        return "STARTING"
    return "RUNNING"


def available_capability(voltage: float, speed_rpm: float) -> Dict[str, float]:
    v_ratio = clamp(voltage / NOMINAL_VOLTAGE, 0.55, 1.15)
    p_avail = P_RATED * v_ratio
    t_avail = (p_avail * 9550.0) / max(speed_rpm, 200.0)
    i_avail = I_SAFE * (0.85 + 0.15 * v_ratio)
    return {"power_kw": p_avail, "torque_nm": t_avail, "current_a": i_avail, "voltage_ratio": v_ratio}


def predict_operating_point(
    sensors: Dict[str, float],
    motor: Dict[str, Any],
    hypothesis: Dict[str, Any],
    situation: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Step the Motor 01 relationships from the live sample to a hypothesized operating point."""
    situation = situation or {}
    mode = infer_mode(motor, sensors)
    bearing = infer_bearing(sensors, situation)
    overheat = infer_overheat(sensors, situation)

    live_load = float(sensors.get("load") or NOMINAL_LOAD)
    live_speed = float(sensors.get("speed") or 0.0)
    live_voltage = float(sensors.get("voltage") or NOMINAL_VOLTAGE)
    live_current = float(sensors.get("current") or NOMINAL_CURRENT)
    live_temp = float(sensors.get("temperature") or NOMINAL_TEMP)
    live_vib = float(sensors.get("vibration") or NOMINAL_VIB)
    live_setpoint = float(sensors.get("speed_setpoint") or NOMINAL_SPEED)

    stopped = bool(hypothesis.get("stopped")) or mode == "STOPPED"
    load = clamp(float(hypothesis.get("load", live_load)), 0.0, 110.0)
    voltage = clamp(float(hypothesis.get("voltage", live_voltage)), 160.0, 280.0)
    cooling = clamp(float(hypothesis.get("cooling", 1.0)), 0.30, 1.0)
    duration_min = max(0.0, float(hypothesis.get("duration_min") or 15.0))

    if hypothesis.get("frequency") is not None:
        setpoint = speed_from_frequency(float(hypothesis["frequency"]))
    else:
        setpoint = float(hypothesis.get("speed", live_setpoint or NOMINAL_SPEED))
    setpoint = clamp(setpoint, 0.0, 1800.0)

    if stopped:
        speed = 0.0
        current = 0.35
        power = electrical_power_kw(voltage, current)
        torque = 0.0
        tau = TAU_MINUTES / max(cooling, 0.3)
        frac = 1.0 - math.exp(-duration_min / tau)
        temperature = live_temp + (AMBIENT + 4.0 - live_temp) * frac
        vibration = live_vib * 0.35
        efficiency = 0.0
        freq = 0.0
        predicted = {
            "load": load,
            "speed": 0.0,
            "speed_setpoint": setpoint,
            "voltage": voltage,
            "frequency": 0.0,
            "current": round(current, 3),
            "power": round(power, 3),
            "torque": 0.0,
            "temperature": round(temperature, 2),
            "vibration": round(vibration, 3),
            "efficiency": 0.0,
            "bearing": round(bearing, 3),
            "overheat": round(overheat, 3),
            "cooling": cooling,
            "duration_min": duration_min,
            "mode": "STOPPED",
        }
        return predicted

    # Speed: track setpoint with load droop and PlantIQ bearing/overheat droop.
    droop = 0.35 * max(0.0, load - NOMINAL_LOAD) + 60.0 * bearing + 20.0 * overheat
    target_speed = max(0.0, setpoint - droop)
    if mode == "STARTING":
        ramp = clamp(duration_min / 2.0, 0.15, 1.0)
        speed = live_speed + (target_speed - live_speed) * ramp
    else:
        speed = target_speed

    # Current demand scales with load vs the live operating point, PlantIQ extras, and voltage.
    load_ratio = load / max(live_load, 8.0)
    voltage_stress = NOMINAL_VOLTAGE / max(voltage, 160.0)
    current_live_scaled = live_current * load_ratio * (live_voltage / max(voltage, 160.0))
    current_from_model = NOMINAL_CURRENT * (load / NOMINAL_LOAD) * voltage_stress + 4.9 * bearing + 1.4 * overheat
    current = 0.45 * current_live_scaled + 0.55 * current_from_model
    current = clamp(current, 0.4, 22.0)

    power = electrical_power_kw(voltage, current)
    torque = torque_nm(power, speed)
    freq = frequency_hz(speed)

    p_mech = mechanical_power_kw(torque, speed)
    efficiency = 0.0 if power <= 0.05 else clamp(p_mech / power, 0.45, 0.96)
    # Efficiency falls at overload, low voltage, and bearing drag.
    efficiency -= 0.10 * max(0.0, load - 80.0) / 20.0
    efficiency -= 0.08 * bearing
    efficiency -= 0.06 * max(0.0, 1.0 - voltage / NOMINAL_VOLTAGE)
    efficiency = clamp(efficiency, 0.48, 0.94)

    # Thermal: first-order lag toward a load/current/cooling steady state.
    t_ss = 48.0 + 0.22 * load + 1.15 * max(0.0, current - NOMINAL_CURRENT)
    t_ss += 22.0 * bearing + 12.0 * overheat
    t_ss += 16.0 * (1.0 - cooling)
    t_ss = clamp(t_ss, AMBIENT + 4.0, 105.0)
    tau = TAU_MINUTES / max(cooling, 0.3)
    frac = 1.0 - math.exp(-duration_min / tau)
    temperature = live_temp + (t_ss - live_temp) * frac

    # Vibration: PlantIQ baseline + load + speed (misalignment) + bearing + overload.
    vib_ss = NOMINAL_VIB + 0.012 * max(0.0, load - 20.0)
    vib_ss += 5.3 * bearing + 0.4 * overheat
    vib_ss += max(0.0, speed / max(NOMINAL_SPEED, 1.0) - 1.0) * 1.4
    vib_ss += max(0.0, load - 85.0) * 0.035
    vib_ss = clamp(vib_ss, 0.6, 12.0)
    vib_frac = 1.0 - math.exp(-duration_min / 10.0)
    vibration = live_vib + (vib_ss - live_vib) * max(0.35, vib_frac)

    if hypothesis.get("vibration") is not None:
        vibration = clamp(float(hypothesis["vibration"]), 0.2, 12.0)
        bearing = clamp((vibration - NOMINAL_VIB) / 5.3, 0.0, 1.0)
        if hypothesis.get("current") is None:
            current = clamp(current + 4.9 * max(0.0, bearing - infer_bearing(sensors, situation)), 0.4, 22.0)
            power = electrical_power_kw(voltage, current)
            torque = torque_nm(power, speed)
        if hypothesis.get("temperature") is None:
            temperature = clamp(temperature + 10.0 * max(0.0, bearing - infer_bearing(sensors, situation)), AMBIENT + 4.0, 105.0)
    if hypothesis.get("temperature") is not None:
        t_req = clamp(float(hypothesis["temperature"]), AMBIENT, 120.0)
        temperature = live_temp + (t_req - live_temp) * max(0.35, frac)
    if hypothesis.get("current") is not None:
        current = clamp(float(hypothesis["current"]), 0.2, 22.0)
        power = electrical_power_kw(voltage, current)
        torque = torque_nm(power, speed)

    return {
        "load": round(load, 2),
        "speed": round(speed, 2),
        "speed_setpoint": round(setpoint, 2),
        "voltage": round(voltage, 2),
        "frequency": round(freq, 3),
        "current": round(current, 3),
        "power": round(power, 3),
        "torque": round(torque, 3),
        "temperature": round(temperature, 2),
        "vibration": round(vibration, 3),
        "efficiency": round(efficiency * 100.0, 1),
        "bearing": round(bearing, 3),
        "overheat": round(overheat, 3),
        "cooling": cooling,
        "duration_min": duration_min,
        "mode": mode,
        "t_ss": round(t_ss, 2),
        "vib_ss": round(vib_ss, 3),
    }


def operating_margins(predicted: Dict[str, float], voltage: float) -> Dict[str, Any]:
    cap = available_capability(voltage, float(predicted.get("speed") or NOMINAL_SPEED))
    p_req = float(predicted.get("power") or 0.0)
    t_req = float(predicted.get("torque") or 0.0)
    i = float(predicted.get("current") or 0.0)
    temp = float(predicted.get("temperature") or 0.0)
    vib = float(predicted.get("vibration") or 0.0)
    power_margin = cap["power_kw"] - p_req
    torque_margin = cap["torque_nm"] - t_req
    current_margin = cap["current_a"] - i
    thermal_margin = T_WARN - temp
    mech_margin = VIB_WARN - vib

    def status(margin: float, warn: float, crit: float) -> str:
        if margin <= crit:
            return "CRITICAL"
        if margin <= warn:
            return "TIGHT"
        return "HEALTHY"

    return {
        "power": {"required": round(p_req, 3), "available": round(cap["power_kw"], 3), "margin": round(power_margin, 3), "unit": "kW", "status": status(power_margin, 0.35, 0.0)},
        "torque": {"required": round(t_req, 2), "available": round(cap["torque_nm"], 2), "margin": round(torque_margin, 2), "unit": "Nm", "status": status(torque_margin, 2.0, 0.0)},
        "current": {"required": round(i, 3), "available": round(cap["current_a"], 3), "margin": round(current_margin, 3), "unit": "A", "status": status(current_margin, 1.2, 0.0)},
        "thermal": {"required": round(temp, 2), "available": T_WARN, "margin": round(thermal_margin, 2), "unit": "°C", "status": status(thermal_margin, 4.0, 0.0)},
        "mechanical": {"required": round(vib, 3), "available": VIB_WARN, "margin": round(mech_margin, 3), "unit": "mm/s", "status": status(mech_margin, 1.0, 0.0)},
        "capability": cap,
    }


def risk_from_condition(
    predicted: Dict[str, float],
    margins: Dict[str, Any],
    live_risk_score: float,
    health: Optional[float],
    similar: Optional[Dict[str, Any]],
    hypothesis: Dict[str, Any],
    live_sensors: Dict[str, float],
) -> Tuple[int, str, Dict[str, int], str]:
    load = float(predicted["load"])
    current = float(predicted["current"])
    temp = float(predicted["temperature"])
    vib = float(predicted["vibration"])
    duration = float(predicted.get("duration_min") or 15.0)
    bearing = float(predicted.get("bearing") or 0.0)
    cooling = float(predicted.get("cooling") or 1.0)
    mode = predicted.get("mode") or "RUNNING"

    load_stress = int(round(clamp((load - 40.0) * 0.55, 0, 22)))
    electrical_stress = int(round(clamp((current - 10.2) * 2.4, 0, 22)))
    if current > I_SAFE:
        electrical_stress = min(28, electrical_stress + 8)
    thermal_stress = int(round(clamp((temp - 62.0) * 0.9, 0, 22)))
    if temp >= T_CRIT:
        thermal_stress = min(28, thermal_stress + 8)
    mechanical_stress = int(round(clamp((vib - 2.8) * 4.2, 0, 24)))
    if vib >= VIB_CRIT:
        mechanical_stress = min(30, mechanical_stress + 8)

    margin_penalty = 0
    for key in ("power", "current", "thermal", "mechanical"):
        m = float(margins[key]["margin"])
        if m <= 0:
            margin_penalty += 12
        elif m <= (0.35 if key == "power" else 1.0):
            margin_penalty += 6
    margin_penalty = min(28, margin_penalty)

    health_val = 100.0 if health is None else float(health)
    health_penalty = int(round(clamp((100.0 - health_val) * 0.18 + bearing * 14.0, 0, 20)))

    similar = similar or {}
    hist = 0
    if similar.get("count"):
        hist = min(16, int(similar.get("failure_count") or 0) * 4 + int(similar.get("count") or 0))
        if (similar.get("matches") or []) and vib >= 4.0:
            hist = min(18, hist + 4)

    duration_penalty = 0
    if load >= 80 or temp >= 72 or vib >= 4.5:
        duration_penalty = int(round(clamp(duration / 60.0 * 14.0, 0, 16)))
    if cooling < 0.6:
        duration_penalty = min(18, duration_penalty + 6)

    live_load = float(live_sensors.get("load") or load)
    abrupt = hypothesis.get("abrupt")
    if abrupt is None:
        abrupt = abs(load - live_load) >= 25
    abrupt_penalty = 8 if abrupt and abs(load - live_load) >= 25 else (4 if abrupt else 0)

    if mode == "STOPPED":
        score = min(28, 8 + int(bearing * 10) + int(overheat_term(predicted)))
        factors = {
            "load_stress": 0,
            "electrical_stress": 0,
            "thermal_stress": min(8, thermal_stress),
            "mechanical_stress": 0,
            "margin_penalty": 0,
            "health_penalty": health_penalty,
            "historical_penalty": 0,
            "duration_penalty": 0,
            "abrupt_penalty": 0,
        }
        return score, level_from_score(score), factors, "stopped"

    score = (
        load_stress
        + electrical_stress
        + thermal_stress
        + mechanical_stress
        + margin_penalty
        + health_penalty
        + hist
        + duration_penalty
        + abrupt_penalty
    )
    score = int(clamp(score, 0, 100))
    if vib >= 8.0 or (vib >= 6.5 and temp >= 90):
        score = max(score, 82)
    factors = {
        "load_stress": load_stress,
        "electrical_stress": electrical_stress,
        "thermal_stress": thermal_stress,
        "mechanical_stress": mechanical_stress,
        "margin_penalty": margin_penalty,
        "health_penalty": health_penalty,
        "historical_penalty": hist,
        "duration_penalty": duration_penalty,
        "abrupt_penalty": abrupt_penalty,
    }
    return score, level_from_score(score), factors, "running"


def overheat_term(predicted: Dict[str, float]) -> float:
    return float(predicted.get("overheat") or 0.0)


def level_from_score(score: int) -> str:
    if score >= 81:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 41:
        return "MEDIUM"
    if score >= 21:
        return "MONITOR"
    return "LOW"


def live_snapshot(sensors: Dict[str, float]) -> Dict[str, float]:
    voltage = float(sensors.get("voltage") or NOMINAL_VOLTAGE)
    current = float(sensors.get("current") or 0.0)
    speed = float(sensors.get("speed") or 0.0)
    power = float(sensors.get("power") or electrical_power_kw(voltage, current))
    torque = float(sensors.get("torque") or torque_nm(power, speed) if speed else 0.0)
    p_mech = mechanical_power_kw(torque, speed)
    efficiency = 0.0 if power <= 0.05 else clamp(100.0 * p_mech / power, 48.0, 96.0)
    return {
        "load": float(sensors.get("load") or 0.0),
        "speed": speed,
        "speed_setpoint": float(sensors.get("speed_setpoint") or NOMINAL_SPEED),
        "voltage": voltage,
        "frequency": float(sensors.get("frequency") or frequency_hz(speed)),
        "current": current,
        "power": power,
        "torque": torque,
        "temperature": float(sensors.get("temperature") or 0.0),
        "vibration": float(sensors.get("vibration") or 0.0),
        "efficiency": round(efficiency, 1),
    }
