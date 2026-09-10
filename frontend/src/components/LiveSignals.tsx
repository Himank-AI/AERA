"use client";

import { useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn, fmt, prettyName, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";
import { Card } from "./ui";

const KEYS = ["speed", "current", "temperature", "vibration", "load"] as const;

export function LiveSignals() {
  const { assessment, advanced } = useRuntime();
  const [open, setOpen] = useState<string | null>(null);
  const series = assessment?.series || {};
  const sensors = assessment?.sensors || {};
  const deviations = assessment?.deviations || [];

  return (
    <Card kicker="Live signals" title="Recent Motor 01 telemetry">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
        {KEYS.map((key) => {
          const row = deviations.find((item) => item.name === key);
          const data = (series[key] || []).map((point, i) => ({ i, v: point.v }));
          const trend = row?.percent_change || 0;
          return (
            <button key={key} onClick={() => setOpen(open === key ? null : key)} className={cn("rounded-lg border p-2 text-left", open === key ? "border-[#2f9e44]" : "border-[#e6edf2]")}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-widest text-[#5b7388]">{prettyName(key)}</span>
                {Math.abs(trend) >= 4 && (
                  <span className={trend > 0 ? "text-[#d45a16]" : "text-[#1b7a38]"}>
                    {trend > 0 ? "↑" : "↓"} {fmt(Math.abs(trend), 0)}%
                  </span>
                )}
              </div>
              <div className="font-mono-aera text-lg">
                {fmt(sensors[key])} <span className="text-xs text-[#5b7388]">{UNITS[key]}</span>
              </div>
              <div className="h-12">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data}>
                    <Line type="monotone" dataKey="v" stroke="#12233a" dot={false} strokeWidth={1.6} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </button>
          );
        })}
      </div>
      {open && (
        <div className="mt-4 h-48 rounded-lg border border-[#e6edf2] p-3">
          <div className="mb-2 text-sm font-semibold">{prettyName(open)} · {fmt(sensors[open])} {UNITS[open]}</div>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={(series[open] || []).map((point, i) => ({ i, v: point.v }))}>
              <XAxis dataKey="i" hide />
              <YAxis domain={["auto", "auto"]} width={40} />
              {advanced && <Tooltip />}
              <Line type="monotone" dataKey="v" stroke="#1d5f8a" dot={false} strokeWidth={2} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
