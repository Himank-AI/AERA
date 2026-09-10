"use client";

import { Card } from "./ui";
import { fmt } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

const P_RATED = 232 * 15.9 * 0.001 * 0.92;

export function MarginCard() {
  const { assessment } = useRuntime();
  const sensors = assessment?.sensors || {};
  const voltage = sensors.voltage || 232;
  const power = sensors.power || 0;
  const available = P_RATED * (voltage / 232);
  const margin = available - power;
  const status = margin <= 0 ? "CRITICAL" : margin < 0.35 ? "MEDIUM" : "NORMAL";
  return (
    <Card kicker="Operating margin" title={`${margin >= 0 ? "+" : ""}${fmt(margin)} kW`}>
      <div className={`inline-flex rounded-md px-2 py-1 text-xs font-semibold risk-${status}`}>{status === "NORMAL" ? "Healthy" : status === "MEDIUM" ? "Tight" : "Critical"}</div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-[#5b7388]">Demand vs capability</summary>
        <div className="mt-2 space-y-1 text-sm text-[#5b7388]">
          <div>Required {fmt(power)} kW</div>
          <div>Available {fmt(available)} kW</div>
        </div>
      </details>
    </Card>
  );
}
