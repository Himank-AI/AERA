"use client";

import { attentionLabel, attentionTone, cn, factorLabel, fmt, secondsAgo } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";
import { Bar, Button, Card } from "./ui";

export function SituationCard({ onEvidence, onQuiet }: { onEvidence?: () => void; onQuiet?: () => void }) {
  const { assessment, experience, lastSeen } = useRuntime();
  const risk = assessment?.risk;
  const situation = assessment?.situation;
  const ago = lastSeen ? Math.max(0, Math.round((Date.now() - lastSeen) / 1000)) : secondsAgo(assessment?.timestamp);
  const label = attentionLabel(risk?.level);
  const quiet = !risk?.level || risk.level === "NORMAL" || risk.level === "MONITOR";

  return (
    <Card className="h-full">
      <div className="kicker">Current situation</div>
      <div className={cn("mt-3 inline-flex rounded-md px-3 py-1.5 text-lg font-semibold tracking-wide", attentionTone(risk?.level))}>
        ● {situation?.title || label}
      </div>
      <p className="mt-4 max-w-3xl text-base leading-7">
        {quiet
          ? assessment?.narrative || "Motor is operating normally under the current operating conditions."
          : experience === "NEW"
            ? assessment?.narrative
            : risk?.reason}
      </p>
      <div className="mt-4 grid max-w-md grid-cols-2 gap-3 text-sm">
        <div>
          <div className="kicker">Attention</div>
          <div className="font-semibold">{label}</div>
        </div>
        <div>
          <div className="kicker">Confidence</div>
          <div className="font-semibold">{risk?.historical_frequency ? "High" : assessment?.connected ? "Moderate" : "None"}</div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button onClick={onEvidence}>Why?</Button>
        <Button variant="ghost" onClick={onQuiet}>Why not flagged</Button>
        <span className="text-xs text-[#5b7388]">{ago == null ? "—" : ago < 5 ? "just now" : `${ago} seconds ago`}</span>
      </div>
      {experience === "EXPERIENCED" && (
        <details className="mt-4 text-xs text-[#5b7388]">
          <summary className="cursor-pointer">Technical details</summary>
          <div className="mt-2 space-y-1 font-mono-aera">
            <div>score {risk?.score ?? "—"} · trend {risk?.trend || "—"}</div>
            <div>historical frequency {risk?.historical_frequency ?? "—"}</div>
            <div>evaluated {assessment?.timestamp || "—"}</div>
          </div>
        </details>
      )}
    </Card>
  );
}

export function AttentionScore() {
  const { assessment } = useRuntime();
  const risk = assessment?.risk;
  const factors = Object.entries(risk?.factors || {});
  const score = risk?.score ?? 0;
  return (
    <Card kicker="AERA attention" title={`${score} / 100`}>
      <div className={cn("inline-flex rounded-md px-2 py-1 text-xs font-semibold", attentionTone(risk?.level))}>
        {attentionLabel(risk?.level)}
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-[#5b7388]">Why this score</summary>
        <p className="mt-2 text-sm text-[#5b7388]">
          {risk?.reason || "Attention is stable because live Motor 01 values match the expected operating pattern."}
        </p>
        <div className="mt-3 space-y-2">
          {factors.map(([key, value]) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-[#5b7388]">{factorLabel(key)}</span>
              <span className="font-mono-aera">{value > 0 ? `+${value}` : value}</span>
            </div>
          ))}
          {!factors.length && <div className="text-sm text-[#5b7388]">No attention contributors on the current sample.</div>}
        </div>
      </details>
    </Card>
  );
}

export function HealthCard() {
  const { assessment } = useRuntime();
  const deviations = assessment?.deviations || [];
  const overallRaw = assessment?.health ?? 0;
  const overall = overallRaw > 0 ? overallRaw : Math.max(8, 100 - (assessment?.risk?.score || 0));
  const condition = overall >= 80 ? "Healthy" : overall >= 60 ? "Watch" : "Degraded";
  const part = (keys: string[]) => {
    const rows = deviations.filter((row) => keys.includes(row.name));
    if (!rows.length) return overall;
    const penalty = rows.reduce((sum, row) => sum + (row.severity === "critical" ? 28 : row.severity === "warning" ? 14 : row.unusual ? 6 : 0), 0);
    return Math.max(4, Math.min(99, overall - penalty));
  };
  const items = [
    { label: "Mechanical", value: part(["vibration", "speed", "torque"]) },
    { label: "Thermal", value: part(["temperature"]) },
    { label: "Electrical", value: part(["current", "voltage", "power"]) },
    { label: "Operating", value: part(["load", "speed"]) },
  ];
  return (
    <Card kicker="Motor condition" title={condition}>
      <div className="font-mono-aera text-2xl">{overall}%</div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-[#5b7388]">Breakdown</summary>
        <div className="mt-3 space-y-3">
          {items.map((item) => (
            <div key={item.label}>
              <div className="mb-1 flex justify-between text-sm">
                <span>{item.label}</span>
                <span className="font-mono-aera">{item.value}%</span>
              </div>
              <Bar value={item.value} tone={item.value >= 90 ? "green" : item.value >= 75 ? "amber" : "red"} />
            </div>
          ))}
        </div>
      </details>
    </Card>
  );
}
