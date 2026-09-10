"use client";

import { useEffect, useRef, useState } from "react";
import { Badge, Bar, Card, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { attentionTone, cn, fmt } from "@/lib/format";
import { useRuntime, useHydrated } from "@/lib/runtime";

const DURATIONS = [5, 15, 30, 60];
const COOLING = [
  { label: "Normal", value: 1 },
  { label: "Restricted", value: 0.55 },
  { label: "Failed", value: 0.35 },
];

function deltaClass(trend?: string) {
  if (trend === "up") return "text-[#d45a16]";
  if (trend === "down") return "text-[#1b7a38]";
  return "text-[#5b7388]";
}

export default function WhatIfPage() {
  const { assessment } = useRuntime();
  const hydrated = useHydrated();
  const sensors = assessment?.sensors || {};
  const primed = useRef(false);
  const [load, setLoad] = useState(64);
  const [speed, setSpeed] = useState(1450);
  const [voltage, setVoltage] = useState(232);
  const [cooling, setCooling] = useState(1);
  const [duration, setDuration] = useState(15);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (primed.current || !sensors.load) return;
    primed.current = true;
    setLoad(Math.round(sensors.load));
    setSpeed(Math.round(sensors.speed_setpoint || sensors.speed || 1450));
    setVoltage(Math.round(sensors.voltage || 232));
  }, [sensors.load, sensors.speed, sensors.speed_setpoint, sensors.voltage]);

  useEffect(() => {
    if (!assessment?.connected) return;
    const handle = window.setTimeout(() => {
      api.whatIf({
        load,
        speed,
        voltage,
        frequency: speed / 30,
        cooling,
        duration_min: duration,
        abrupt: Math.abs(load - (sensors.load || load)) >= 25,
      })
        .then((row) => {
          if (row.error) {
            setError(row.error);
            return;
          }
          setError("");
          setResult(row);
        })
        .catch(() => setError("What-If service is unavailable."));
    }, 160);
    return () => window.clearTimeout(handle);
  }, [assessment?.connected, load, speed, voltage, cooling, duration, sensors.load]);

  const resetLive = () => {
    setLoad(Math.round(sensors.load || 64));
    setSpeed(Math.round(sensors.speed_setpoint || sensors.speed || 1450));
    setVoltage(Math.round(sensors.voltage || 232));
    setCooling(1);
    setDuration(15);
  };

  if (!hydrated || !assessment) return <Loading />;

  const predicted = result?.predicted || {};
  const current = result?.current || {};
  const risk = result?.risk || {};
  const margins = result?.margins || {};

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="kicker">AERA · What-If · SIMULATION ONLY</div>
          <h1 className="text-2xl font-semibold">What happens if I change something?</h1>
          <p className="text-sm text-[#d45a16]">Predicted values are not live motor data. No commands will be sent.</p>
        </div>
        <button className="rounded-md border border-[#d9e1e8] px-3 py-1.5 text-xs" onClick={resetLive}>Reset to live</button>
      </div>

      {error && <div className="rounded-xl border border-[#c62828] bg-[#f8d6d6] p-3 text-sm">{error}</div>}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card kicker="SCENARIO INPUT" title="Hypothesis — not a live command">
          <label className="mb-3 block text-sm">Load {load}%
            <input type="range" min={15} max={100} value={load} onChange={(e) => setLoad(Number(e.target.value))} className="w-full" />
          </label>
          <label className="mb-3 block text-sm">Speed setpoint {speed} RPM · {fmt(speed / 30, 1)} Hz
            <input type="range" min={800} max={1600} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="w-full" />
          </label>
          <label className="mb-3 block text-sm">Voltage {voltage} V
            <input type="range" min={180} max={260} value={voltage} onChange={(e) => setVoltage(Number(e.target.value))} className="w-full" />
          </label>
          <div className="mb-3 text-sm">
            <div className="mb-1">Cooling</div>
            <div className="flex flex-wrap gap-1">
              {COOLING.map((item) => (
                <button key={item.label} onClick={() => setCooling(item.value)} className={cn("rounded-full px-3 py-1 text-xs", cooling === item.value ? "bg-[#12233a] text-white" : "border border-[#d9e1e8]")}>
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="text-sm">
            <div className="mb-1">Duration</div>
            <div className="flex flex-wrap gap-1">
              {DURATIONS.map((item) => (
                <button key={item} onClick={() => setDuration(item)} className={cn("rounded-full px-3 py-1 text-xs", duration === item ? "bg-[#12233a] text-white" : "border border-[#d9e1e8]")}>
                  {item < 60 ? `${item} min` : "1 hour"}
                </button>
              ))}
            </div>
          </div>
        </Card>

        <Card kicker="WHAT-IF / PREDICTED" title="Not live motor data" action={<Badge level={risk.level}>{risk.level || "—"}</Badge>}>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {[
              ["Speed", current.speed, predicted.speed, "RPM"],
              ["Current", current.current, predicted.current, "A"],
              ["Power", current.power, predicted.power, "kW"],
              ["Temperature", current.temperature, predicted.temperature, "°C"],
              ["Vibration", current.vibration, predicted.vibration, "mm/s"],
              ["Efficiency", current.efficiency, predicted.efficiency, "%"],
            ].map(([label, before, after, unit]) => {
              const delta = Number(after || 0) - Number(before || 0);
              return (
                <div key={String(label)} className="rounded-lg border border-[#e6edf2] p-3">
                  <div className="kicker">{label}</div>
                  <div className="font-mono-aera text-lg">{fmt(after as number)} <span className="text-xs text-[#5b7388]">{unit}</span></div>
                  <div className={cn("text-[11px]", deltaClass(delta > 0.05 ? "up" : delta < -0.05 ? "down" : "flat"))}>
                    {fmt(before as number)} → {delta >= 0 ? "+" : ""}{fmt(delta)}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Card kicker="AERA predicted risk" title={`${risk.score ?? "—"} / 100`}>
          <div className={cn("inline-flex rounded-md px-2 py-1 text-xs font-semibold", attentionTone(risk.level === "LOW" ? "NORMAL" : risk.level))}>
            {risk.level || "—"}
          </div>
          <p className="mt-2 text-xs text-[#5b7388]">Live {risk.before ?? "—"} / 100 → predicted {risk.score ?? "—"} / 100</p>
          <div className="mt-3 space-y-2">
            {(result?.risk?.contributors || []).map((row: any) => (
              <div key={row.label}>
                <div className="mb-1 flex justify-between text-xs">
                  <span>{row.label}</span>
                  <span className="font-mono-aera">+{row.points}</span>
                </div>
                <Bar value={Math.min(100, row.points * 4)} tone={row.points >= 12 ? "red" : row.points >= 6 ? "amber" : "blue"} />
              </div>
            ))}
          </div>
        </Card>
        <Card kicker="Operating margin" title="Demand vs capability">
          {["power", "current", "thermal", "mechanical"].map((key) => {
            const row = margins[key];
            if (!row) return null;
            return (
              <div key={key} className="mb-3 grid grid-cols-[110px_1fr_auto] items-center gap-2 text-sm">
                <div className="uppercase tracking-widest text-[10px] text-[#5b7388]">{key}</div>
                <div>
                  Required {fmt(row.required)} {row.unit} · available {fmt(row.available)} {row.unit}
                </div>
                <Badge level={row.status === "HEALTHY" ? "NORMAL" : row.status === "TIGHT" ? "MEDIUM" : "CRITICAL"}>
                  {row.margin >= 0 ? "+" : ""}{fmt(row.margin)} {row.unit}
                </Badge>
              </div>
            );
          })}
        </Card>
      </div>

      <Card kicker="Why did risk change?" title="Causal chain">
        <div className="mb-4 space-y-1">
          {(result?.chain || []).map((step: string, index: number) => (
            <div key={step} className="flex flex-col items-center">
              <div className="w-full rounded-lg border border-[#d9e1e8] bg-[#f8fafb] px-3 py-2 text-center text-sm">{step}</div>
              {index < (result?.chain || []).length - 1 && <div className="py-1 text-[#5b7388]">↓</div>}
            </div>
          ))}
        </div>
        <p className="text-sm">{result?.why}</p>
        <div className="mt-3 rounded-lg border border-[#d7e6f0] bg-[#f4f8fb] p-3 text-sm">
          <div className="kicker">Expected outcome</div>
          {result?.expected_outcome}
        </div>
      </Card>

      <Card kicker="Current vs what-if" title="Parameter comparison">
        <div className="overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-[10px] uppercase tracking-widest text-[#5b7388]">
              <tr>
                <th className="py-1">Parameter</th>
                <th>Current</th>
                <th>What-if</th>
                <th>Change</th>
                <th>Impact</th>
              </tr>
            </thead>
            <tbody>
              {(result?.comparison || []).map((row: any) => (
                <tr key={row.parameter} className="border-t border-[#e6edf2]">
                  <td className="py-1.5 capitalize">{row.parameter}</td>
                  <td className="font-mono-aera">{fmt(row.current)} {row.unit}</td>
                  <td className="font-mono-aera">{fmt(row.predicted)} {row.unit}</td>
                  <td className={cn("font-mono-aera", deltaClass(row.trend))}>{row.change > 0 ? "+" : ""}{fmt(row.change)} {row.unit}</td>
                  <td><Badge level={row.impact === "STABLE" ? "NORMAL" : row.impact}>{row.impact}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card kicker="Time-based prediction" title="How the condition may evolve">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {(result?.timeline || []).map((row: any) => (
              <button key={row.minutes} onClick={() => setDuration(row.minutes)} className={cn("rounded-lg border p-3 text-left", duration === row.minutes ? "border-[#2f9e44]" : "border-[#e6edf2]")}>
                <div className="kicker">{row.minutes < 60 ? `${row.minutes} min` : "1 hour"}</div>
                <div className="font-mono-aera">{fmt(row.temperature)}°C</div>
                <div className="text-[11px] text-[#5b7388]">{row.level} · {row.risk_score}</div>
              </button>
            ))}
          </div>
        </Card>
        <Card kicker="Historical intelligence" title={result?.history?.count ? `${result.history.count} similar incidents` : "No comparable incident found"}>
          <p className="text-sm text-[#5b7388]">{result?.history?.summary}</p>
          {(result?.history?.matches || []).slice(0, 3).map((row: any) => (
            <div key={row.event_number} className="mt-2 rounded-lg border border-[#e6edf2] p-2 text-sm">
              INC-{row.event_number} · {row.root_cause} · {row.similarity}%
            </div>
          ))}
        </Card>
      </div>
      <p className="text-xs text-[#5b7388]">Command sent: false. Use the Motor + HMI if a real operating change is required.</p>
    </div>
  );
}
