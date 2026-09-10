"use client";

import Link from "next/link";
import { MotorSchematic } from "@/components/MotorSchematic";
import { fmt, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

export default function MotorOverviewPage() {
  const { assessment } = useRuntime();
  const sensors = assessment?.sensors || {};
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">Motor simulator</div>
        <h1 className="text-2xl font-semibold">Digital representation of the connected motor</h1>
        <p className="text-sm text-[#5b7388]">What the machine is actually doing. AERA explanations live under AERA.</p>
      </div>
      <MotorSchematic />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {[
          ["Current", sensors.current, "current"],
          ["Voltage", sensors.voltage, "voltage"],
          ["Torque", sensors.torque, "torque"],
          ["Power", sensors.power, "power"],
          ["Temperature", sensors.temperature, "temperature"],
          ["Vibration", sensors.vibration, "vibration"],
        ].map(([label, value, key]) => (
          <div key={String(label)} className="card p-3">
            <div className="kicker">{label}</div>
            <div className="font-mono-aera text-lg">
              {fmt(value as number)} {UNITS[String(key)]}
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <Link href="/motor/parameters" className="rounded-md bg-[#12233a] px-3 py-1.5 text-xs text-white">View all parameters</Link>
        <Link href="/motor/faults" className="rounded-md border border-[#d9e1e8] px-3 py-1.5 text-xs">Fault simulation</Link>
        <Link href="/hmi" className="rounded-md border border-[#d9e1e8] px-3 py-1.5 text-xs">Open HMI</Link>
      </div>
    </div>
  );
}
