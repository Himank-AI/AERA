"use client";

import { useMemo, useState } from "react";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, YAxis } from "recharts";
import { cn, fmt, prettyName, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

const KEYS = ["temperature", "vibration", "speed", "load", "current", "voltage"] as const;
const STROKE: Record<string, string> = {
  temperature: "#e08a4a",
  vibration: "#d4a017",
  speed: "#4aa3c2",
  load: "#8aa0b0",
  current: "#7ec8a0",
  voltage: "#9aa8b4",
};

export function StationTrends() {
  const { assessment } = useRuntime();
  const [open, setOpen] = useState<string | null>("temperature");
  const series = assessment?.series || {};
  const sensors = assessment?.sensors || {};
  const deviations = assessment?.deviations || [];
  const alert = Boolean(assessment?.copilot_view?.alert);
  const situation = assessment?.situation?.id;

  const marks = useMemo(() => {
    const out: Record<string, number | null> = {};
    for (const key of KEYS) {
      const row = deviations.find((item) => item.name === key);
      out[key] = row?.unusual ? Number(row.expected) : null;
    }
    return out;
  }, [deviations]);

  return (
    <div>
      <div className="kicker">Live trends</div>
      <div className="mt-2 grid grid-cols-3 gap-2">
        {KEYS.map((key) => {
          const row = deviations.find((item) => item.name === key);
          const data = (series[key] || []).map((point, i) => ({ i, v: point.v }));
          const trend = row?.percent_change || 0;
          const unusual = Boolean(row?.unusual);
          return (
            <button
              key={key}
              onClick={() => setOpen(open === key ? null : key)}
              className={cn(
                "rounded border bg-[#0c1116] p-2 text-left",
                open === key ? "border-[#3a4a56]" : "border-[#1e2a32]",
                unusual && "border-[#5a2a22]",
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-widest text-[#7d8b96]">{prettyName(key)}</span>
                {Math.abs(trend) >= 4 && (
                  <span className={trend > 0 ? "text-[#ffb089]" : "text-[#8ee0a8]"}>
                    {trend > 0 ? "↑" : "↓"} {fmt(Math.abs(trend), 0)}%
                  </span>
                )}
              </div>
              <div className="font-mono-aera text-sm">
                {fmt(sensors[key], key === "speed" || key === "load" ? 0 : 1)}{" "}
                <span className="text-[10px] text-[#7d8b96]">{UNITS[key]}</span>
              </div>
              <div className="h-10">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data}>
                    <Line type="monotone" dataKey="v" stroke={STROKE[key]} dot={false} strokeWidth={1.5} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </button>
          );
        })}
      </div>
      {open && (
        <div className="mt-2 h-36 rounded border border-[#1e2a32] bg-[#0c1116] p-2">
          <div className="mb-1 flex items-center justify-between text-[11px]">
            <span className="font-semibold">
              {prettyName(open)} · {fmt(sensors[open], open === "speed" || open === "load" ? 0 : 1)} {UNITS[open]}
            </span>
            {alert && (open === "vibration" || open === "temperature") && situation !== "high_load_thermal" && (
              <span className="text-[10px] font-bold tracking-widest text-[#ffb0b0]">ALERT ↑ threshold</span>
            )}
          </div>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={(series[open] || []).map((point, i) => ({ i, v: point.v }))}>
              <YAxis domain={["auto", "auto"]} width={36} tick={{ fill: "#7d8b96", fontSize: 10 }} />
              {marks[open] != null && (
                <ReferenceLine y={marks[open] as number} stroke="#5a6a76" strokeDasharray="3 3" />
              )}
              <Line type="monotone" dataKey="v" stroke={STROKE[open]} dot={false} strokeWidth={2} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
