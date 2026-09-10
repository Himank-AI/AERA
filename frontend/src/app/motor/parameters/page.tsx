"use client";

import Link from "next/link";
import { fmt, prettyName, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

export default function MotorParametersPage() {
  const { assessment, advanced } = useRuntime();
  const sensors = assessment?.sensors || {};
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">Motor · Parameters</div>
        <h1 className="text-2xl font-semibold">All Motor 01 signals</h1>
        <Link href="/motor" className="text-xs text-[#1d5f8a]">← Motor overview</Link>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {Object.entries(sensors).map(([key, value]) => (
          <div key={key} className="card p-3">
            <div className="kicker">{prettyName(key)}</div>
            <div className="font-mono-aera text-lg">
              {fmt(value)} {UNITS[key] || ""}
            </div>
          </div>
        ))}
      </div>
      <Link href="/motor/state" className="text-xs text-[#1d5f8a]">Motor state →</Link>
      {advanced && <p className="text-xs text-[#5b7388]">Source: {assessment?.source}</p>}
    </div>
  );
}
