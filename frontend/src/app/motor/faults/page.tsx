"use client";

import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useRuntime } from "@/lib/runtime";

const SCENARIOS = [
  ["Normal", "NORMAL"],
  ["Voltage spike", "VOLTAGE_SPIKE"],
  ["Bearing degradation", "MOTOR_DEGRADATION"],
  ["Overheat", "MOTOR_OVERHEAT"],
];

export default function MotorFaultsPage() {
  const { assessment } = useRuntime();
  const scenario = assessment?.motor?.scenario;
  const run = (name: string) => api.scenario(name).catch(() => undefined);
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">Motor · Fault simulation</div>
        <h1 className="text-2xl font-semibold">Inject a simulated condition</h1>
        <p className="text-sm text-[#d45a16]">DEMO / SIMULATION — forwards to the Motor + HMI simulator. AERA does not command the motor.</p>
      </div>
      <Card kicker="Current scenario" title={scenario && scenario !== "NORMAL" ? scenario : "NORMAL"}>
        <div className="flex flex-wrap gap-2">
          {SCENARIOS.map(([label, id]) => (
            <button key={id} className="rounded-md border border-[#d9e1e8] px-3 py-2 text-sm hover:border-[#2f9e44]" onClick={() => run(id)}>
              {label}
            </button>
          ))}
          <button className="rounded-md border border-[#c62828] px-3 py-2 text-sm text-[#c62828]" onClick={() => api.reset()}>Reset</button>
        </div>
      </Card>
      <p className="text-sm text-[#5b7388]">After injecting a fault, open HMI to see operator telemetry, then AERA to see how intelligence interprets it.</p>
    </div>
  );
}
