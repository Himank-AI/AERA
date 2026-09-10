"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, Button, Empty, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useRuntime } from "@/lib/runtime";

export default function IncidentsPage() {
  return (
    <Suspense fallback={<Loading title="Loading incidents" body="Opening Motor + HMI incident history." />}>
      <IncidentsInner />
    </Suspense>
  );
}

function IncidentsInner() {
  const { assessment } = useRuntime();
  const params = useSearchParams();
  const [history, setHistory] = useState<any>(null);
  const [replay, setReplay] = useState<any>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    api.history().then(setHistory).catch(() => undefined);
  }, []);

  useEffect(() => {
    const n = Number(params.get("event") || 0);
    if (n) api.replay(n).then(setReplay).catch(() => undefined);
  }, [params]);

  const timeline = replay?.timeline || [];
  const current = timeline[step];
  const matches = assessment?.similar?.matches || [];
  const stored = (history?.motor_history || []).slice(0, 12);
  const cards = [
    ...matches.map((row) => ({
      event_number: row.event_number,
      root_cause: row.root_cause,
      severity: row.failure ? "HIGH" : "MEDIUM",
      symptoms: row.symptoms,
      operator_action: row.operator_action,
      outcome: row.outcome,
      similarity: row.similarity,
    })),
    ...stored
      .filter((row: any) => !matches.some((m: any) => m.event_number === row.event_number))
      .slice(0, 6)
      .map((row: any) => ({
        event_number: row.event_number,
        root_cause: row.pattern_family || row.root_cause,
        severity: row.failure ? "HIGH" : "MEDIUM",
        symptoms: row.symptoms || row.description,
        operator_action: row.operator_action,
        outcome: row.outcome,
      })),
  ];

  const open = (n?: number) => {
    if (!n) return;
    setStep(0);
    api.replay(Number(n)).then(setReplay);
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">AERA · Incidents</div>
        <h1 className="text-2xl font-semibold">{replay ? "Incident replay" : "Incident history"}</h1>
        <p className="text-sm text-[#5b7388]">Previous Motor 01 cases. AERA does not invent incidents.</p>
      </div>

      {!replay && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {cards.map((row) => (
            <button
              key={row.event_number}
              className="card p-4 text-left hover:border-[#2f9e44]"
              onClick={() => open(row.event_number)}
            >
              <div className="kicker">INC-{row.event_number}</div>
              <div className="mt-1 font-semibold">{row.root_cause}</div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-[#5b7388]">
                <div>Severity {row.severity}</div>
                {row.similarity != null && <div>Similarity {row.similarity}%</div>}
                <div>Action {row.operator_action || "—"}</div>
                <div>Outcome {row.outcome || "—"}</div>
              </div>
              {row.symptoms && <p className="mt-2 text-xs text-[#5b7388]">{row.symptoms}</p>}
              <div className="mt-3 text-xs font-semibold text-[#1d5f8a]">Replay →</div>
            </button>
          ))}
          {!cards.length && <Empty title="No similar incident" body="When AERA finds a historical match, it will appear here for replay." />}
        </div>
      )}

      {replay && (
        <Card kicker="Incident replay" title={replay.title || "Selected incident"} action={<Button variant="ghost" onClick={() => setReplay(null)}>Back to list</Button>}>
          {timeline.length > 0 && (
            <div className="mb-4 space-y-1">
              {timeline.map((item: any, index: number) => (
                <div key={index} className="flex flex-col items-center">
                  <button
                    onClick={() => setStep(index)}
                    className={`w-full rounded-lg px-3 py-2 text-sm ${index === step ? "bg-[#12233a] text-white" : "border border-[#d9e1e8]"}`}
                  >
                    {item.label}
                  </button>
                  {index < timeline.length - 1 && <div className="py-1 text-[#5b7388]">↓</div>}
                </div>
              ))}
            </div>
          )}
          {current && (
            <div className="rounded-lg border border-[#e6edf2] bg-[#f8fafb] p-3">
              <div className="font-mono-aera text-xs">{current.time}</div>
              <div className="text-lg font-semibold">{current.label}</div>
              <p className="text-sm text-[#5b7388]">{current.detail}</p>
              <div className="mt-4 flex items-center gap-2">
                <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))}>Previous</Button>
                <div className="text-xs">{step + 1} / {timeline.length}</div>
                <Button onClick={() => setStep(Math.min(timeline.length - 1, step + 1))}>Next</Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
