"use client";

import Link from "next/link";
import { Card } from "@/components/ui";
import { fmt, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

export default function MotorStatePage() {
  const { assessment } = useRuntime();
  const motor = assessment?.motor;
  const sensors = assessment?.sensors || {};
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">Motor · State</div>
        <h1 className="text-2xl font-semibold">What the machine is doing</h1>
        <p className="text-sm text-[#5b7388]">Physical status only. Interpretation lives in AERA.</p>
      </div>
      <Card kicker="Operating state" title={motor?.status || "—"}>
        <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
          <div>Mode<div className="font-semibold">{motor?.operating_mode || motor?.status || "—"}</div></div>
          <div>Direction<div className="font-semibold">{motor?.direction || "FWD"}</div></div>
          <div>Drive<div className="font-semibold">{motor?.drive_status || "—"}</div></div>
          <div>Health status<div className="font-semibold">{motor?.health_status || "—"}</div></div>
          <div>Fault state<div className="font-semibold">{String(motor?.fault_state || false)}</div></div>
          <div>Scenario<div className="font-semibold">{motor?.scenario || "NORMAL"}</div></div>
        </div>
      </Card>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {[
          ["Runtime", sensors.runtime, "runtime"],
          ["Energy", sensors.energy, "energy"],
          ["Start cycles", sensors.start_cycles, ""],
          ["Frequency", sensors.frequency, "frequency"],
        ].map(([label, value, key]) => (
          <div key={String(label)} className="card p-3">
            <div className="kicker">{label}</div>
            <div className="font-mono-aera text-lg">
              {fmt(value as number)} {key ? UNITS[String(key)] : ""}
            </div>
          </div>
        ))}
      </div>
      <Link href="/motor/parameters" className="text-xs text-[#1d5f8a]">View all parameters →</Link>
    </div>
  );
}
