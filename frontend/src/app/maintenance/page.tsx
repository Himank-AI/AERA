"use client";

import { FormEvent, useEffect, useState } from "react";
import { Card, Button, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import { useRuntime } from "@/lib/runtime";

export default function MaintenancePage() {
  const { assessment } = useRuntime();
  const [data, setData] = useState<any>({ feedback: [], outcomes: [], incidents: [] });
  const refresh = () => api.learning().then(setData).catch(() => undefined);
  useEffect(() => {
    refresh();
  }, []);

  const onOutcome = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.outcome({
      recommendation: assessment?.risk?.recommended_response,
      operator_action: form.get("operator_action"),
      actual_cause: form.get("actual_cause"),
      actual_solution: form.get("actual_solution"),
      outcome: form.get("outcome"),
      situation: assessment?.situation?.title,
      risk_level: assessment?.risk?.level,
    });
    event.currentTarget.reset();
    refresh();
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">HMI · Maintenance</div>
        <h1 className="text-2xl font-semibold">Motor 01 maintenance</h1>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <div className="card p-3"><div className="kicker">Runtime</div><div className="font-mono-aera text-lg">{Number(assessment?.sensors?.runtime || 0).toFixed(1)} h</div></div>
        <div className="card p-3"><div className="kicker">Start count</div><div className="font-mono-aera text-lg">{Number(assessment?.sensors?.start_cycles || 0).toFixed(0)}</div></div>
        <div className="card p-3"><div className="kicker">Health</div><div className="font-semibold">{assessment?.motor?.health_status || "—"}</div></div>
        <div className="card p-3"><div className="kicker">Inspection</div><div className="text-sm">{assessment?.risk?.recommended_response || "Continue scheduled checks"}</div></div>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card kicker="Record outcome" title="What really happened">
          <form onSubmit={onOutcome} className="grid gap-2 text-sm">
            <input name="operator_action" placeholder="Operator action" className="rounded-md border border-[#d9e1e8] px-3 py-2" />
            <input name="actual_cause" placeholder="Actual root cause" className="rounded-md border border-[#d9e1e8] px-3 py-2" />
            <input name="actual_solution" placeholder="Actual solution" className="rounded-md border border-[#d9e1e8] px-3 py-2" />
            <input name="outcome" placeholder="Outcome" className="rounded-md border border-[#d9e1e8] px-3 py-2" />
            <Button type="submit">Store incident learning</Button>
          </form>
        </Card>
        <Card kicker="Previous solutions" title="From Motor + HMI / experts">
          {(assessment?.guidance?.previous_solutions || []).map((row, index) => (
            <div key={index} className="mb-2 text-sm">
              <div className="font-semibold">{row.root_cause || row.action}</div>
              <div className="text-[#5b7388]">{row.outcome}</div>
            </div>
          ))}
          {!(assessment?.guidance?.previous_solutions || []).length && <Empty title="No stored solution yet" body="Resolved incidents will appear here after they are recorded." />}
        </Card>
      </div>
      <Card kicker="Feedback" title="Operator responses">
        {(data.feedback || []).slice().reverse().map((row: any) => (
          <div key={row.id} className="border-b border-[#e6edf2] py-2 text-sm">
            {row.feedback_type} · {row.situation} · {row.risk_level}
          </div>
        ))}
      </Card>
      <Card kicker="Learned incidents">
        {(data.incidents || []).slice().reverse().map((row: any) => (
          <div key={row.id} className="mb-2 rounded-lg border border-[#e6edf2] p-3 text-sm">
            <div className="font-semibold">{row.incident}</div>
            <div>Cause: {row.actual_root_cause}</div>
            <div>Solution: {row.solution}</div>
            <div>Outcome: {row.outcome}</div>
          </div>
        ))}
      </Card>
    </div>
  );
}
