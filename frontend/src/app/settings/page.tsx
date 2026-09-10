"use client";

import { Card } from "@/components/ui";
import { useRuntime } from "@/lib/runtime";

export default function SettingsPage() {
  const { connected, assessment, experience, setExperience } = useRuntime();
  const live = connected && assessment?.connected;
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">Settings</div>
        <h1 className="text-2xl font-semibold">Operator and connection</h1>
      </div>
      <Card kicker="View mode" title="Operator vs advanced">
        <p className="mb-3 text-sm text-[#5b7388]">Operator view uses plain language, actions, and historical context. Advanced view adds raw telemetry, thresholds, and evidence scores.</p>
        <select value={experience} onChange={(e) => setExperience(e.target.value)} className="rounded-md border border-[#d9e1e8] px-3 py-2 text-sm">
          <option value="NEW">Operator view</option>
          <option value="EXPERIENCED">Advanced view</option>
        </select>
      </Card>
      <Card kicker="Connection" title={live ? "Motor connected" : connected ? "Motor disconnected" : "Reconnecting"}>
        <div className="space-y-1 text-sm">
          <div>AERA backend: {connected ? "online" : "reconnecting"}</div>
          <div>Motor + HMI data: {assessment?.connected ? "live telemetry" : "not received"}</div>
          <div>Source: {assessment?.source || "none"}</div>
          <div>Last sample: {assessment?.timestamp || "—"}</div>
          <div className="mt-2 text-[#5b7388]">AERA never starts, stops, or resets the motor. Demo buttons only forward scenarios to the Motor + HMI simulator.</div>
        </div>
      </Card>
    </div>
  );
}
