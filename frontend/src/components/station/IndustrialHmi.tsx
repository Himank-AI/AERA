"use client";

import { useRef } from "react";
import { api } from "@/lib/api";
import { attentionTone, cn, fmt, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";
import type { Assessment } from "@/lib/types";

const ROWS: Array<{ key: string; label: string; step: number; digits?: number }> = [
  { key: "load", label: "LOAD", step: 5, digits: 0 },
  { key: "speed", label: "RPM", step: 50, digits: 0 },
  { key: "temperature", label: "TEMP", step: 1 },
  { key: "vibration", label: "VIB", step: 0.5 },
  { key: "current", label: "CURRENT", step: 0.5 },
  { key: "voltage", label: "VOLT", step: 2, digits: 0 },
];

export function IndustrialHmi() {
  const { assessment, applyAssessment } = useRuntime();
  const sensors = assessment?.sensors || {};
  const mode = (assessment?.motor?.status || "STOPPED").toUpperCase();
  const running = mode === "RUNNING" || mode === "STARTING";
  const stopped = mode === "STOPPED";
  const alarms = assessment?.alarms || [];
  const machine = String(assessment?.motor?.health_status || "NORMAL").toUpperCase();
  const clock = (assessment?.timestamp || "").slice(11, 19);
  const alarm = (alarms[0] || {}) as Record<string, unknown>;
  const pending = useRef<Record<string, number>>({});

  const push = async (job: Promise<Assessment | Record<string, unknown>>) => {
    const row = await job.catch(() => undefined);
    if (!row) return;
    const payload = (row as { state?: Assessment }).state || row;
    applyAssessment(payload as Assessment);
  };

  const bump = (key: string, step: number) => {
    const current = pending.current[key] ?? Number(sensors[key] ?? 0);
    const nextVal = Number((current + step).toFixed(2));
    pending.current[key] = nextVal;
    if (assessment?.sensors) {
      applyAssessment({ ...assessment, sensors: { ...sensors, [key]: nextVal } });
    }
    void push(api.setParam(key, nextVal)).then(() => {
      if (pending.current[key] === nextVal) delete pending.current[key];
    });
  };

  return (
    <div className="hmi-bezel min-h-[280px] shrink-0 p-2">
      <div className="mb-1 flex items-center justify-between px-1 text-[10px] uppercase tracking-[0.16em] text-[#7d8b96]">
        <span>HMI · MOTOR-01</span>
        <span className="font-mono-aera">{clock || "--:--:--"}</span>
      </div>
      <div className="hmi-glass p-3">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="kicker">Motor status</div>
            <div className="text-lg font-semibold">{machine === "ALARM" ? "ALARM" : mode}</div>
          </div>
          <div className={cn("rounded px-2 py-1 text-[11px] font-bold tracking-widest", attentionTone(machine === "ALARM" ? "CRITICAL" : machine === "ANOMALY" ? "ATTENTION" : "NORMAL"))}>
            {machine === "ALARM" ? "ALARM" : machine === "ANOMALY" ? "ANOMALY" : "NORMAL"}
          </div>
        </div>

        <div className="mb-3 grid grid-cols-3 gap-2">
          {ROWS.map((row) => (
            <div key={row.key} className="rounded border border-[#1e2a32] bg-[#0b1116] px-2 py-1.5">
              <div className="flex items-center justify-between">
                <span className="kicker">{row.label}</span>
                <span className="text-[10px] text-[#7d8b96]">{UNITS[row.key]}</span>
              </div>
              <div className="mt-0.5 flex items-center justify-between gap-1">
                <button className="h-6 w-6 rounded border border-[#2a3640] text-xs" onClick={() => bump(row.key, -row.step)}>−</button>
                <div className="font-mono-aera text-sm">{fmt(sensors[row.key], row.digits ?? 1)}</div>
                <button className="h-6 w-6 rounded border border-[#2a3640] text-xs" onClick={() => bump(row.key, row.step)}>+</button>
              </div>
            </div>
          ))}
        </div>

        <div className="mb-3 grid grid-cols-3 gap-2">
          <button className="hmi-btn start" disabled={running} onClick={() => void push(api.start())}>Start</button>
          <button className="hmi-btn stop" disabled={stopped} onClick={() => void push(api.stop())}>Stop</button>
          <button className="hmi-btn reset" onClick={() => void push(api.reset())}>Reset</button>
        </div>

        <div className="mt-2 flex items-start justify-between gap-2 text-[11px]">
          <div className={cn("min-w-0", alarms.length ? "text-[#ffb0b0]" : "text-[#7d8b96]")}>
            {alarms.length ? (
              <div>
                <div className="font-bold tracking-widest">ALARM · {String(alarm.title || alarm.name || "ACTIVE")}</div>
                <div className="font-mono-aera text-[10px] text-[#d5dee6]">
                  {fmt(Number(alarm.value))} {String(alarm.unit || "")} · {String(alarm.condition || "Above threshold")} · {String(alarm.clock || "")}
                </div>
              </div>
            ) : (
              "NO ACTIVE ALARM"
            )}
          </div>
          <div className="flex shrink-0 gap-1">
            <button className="rounded border border-[#2a3640] px-2 py-1 text-[10px] uppercase tracking-widest" onClick={() => void push(api.scenario("MOTOR_DEGRADATION"))}>Bearing</button>
            <button className="rounded border border-[#2a3640] px-2 py-1 text-[10px] uppercase tracking-widest" onClick={() => void push(api.scenario("NORMAL"))}>Clear</button>
          </div>
        </div>
      </div>
    </div>
  );
}
