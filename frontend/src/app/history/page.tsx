"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, Empty, Loading } from "@/components/ui";
import { EventTimeline } from "@/components/Intelligence";
import { api } from "@/lib/api";
import { useRuntime } from "@/lib/runtime";

export default function HistoryPage() {
  return (
    <Suspense fallback={<Loading title="Loading history" body="Reading Motor + HMI historical events." />}>
      <HistoryInner />
    </Suspense>
  );
}

function HistoryInner() {
  const { search } = useRuntime();
  const params = useSearchParams();
  const q = (params.get("q") || search || "").toLowerCase();
  const [tab, setTab] = useState<"events" | "incidents" | "actions">("events");
  const [history, setHistory] = useState<any>(null);

  useEffect(() => {
    api.history().then(setHistory).catch(() => undefined);
  }, []);

  const events = useMemo(() => {
    const list = history?.motor_history || [];
    if (!q) return list;
    return list.filter((row: any) => JSON.stringify(row).toLowerCase().includes(q));
  }, [history, q]);
  const incidents = history?.incidents || [];
  const actions = history?.actions || [];

  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">AERA · History</div>
        <h1 className="text-2xl font-semibold">Motor 01 historical memory</h1>
      </div>
      <div className="flex gap-1">
        {(["events", "incidents", "actions"] as const).map((item) => (
          <button key={item} onClick={() => setTab(item)} className={`rounded-full px-3 py-1 text-xs ${tab === item ? "bg-[#12233a] text-white" : "border border-[#d9e1e8]"}`}>
            {item}
          </button>
        ))}
      </div>
      {tab === "events" && (
        <>
          <EventTimeline />
          <Card kicker="Events" title={q ? `Filtered by “${q}”` : "Stored Motor + HMI events"}>
          {!events.length && <Empty title="No matching events" body="AERA only lists events that exist in the Motor + HMI history." />}
          <div className="max-h-[28rem] overflow-auto">
            {events.slice(0, 40).map((row: any) => (
              <div key={row.event_number || row.id} className="grid grid-cols-2 gap-2 border-b border-[#e6edf2] py-2 text-xs md:grid-cols-5">
                <div>{(row.timestamp || "").slice(0, 19)}</div>
                <div>{row.pattern_family}</div>
                <div>{row.outcome}</div>
                <div>{row.operator_action || "—"}</div>
                <div>{row.failure ? "trip/failure" : "no trip"}</div>
              </div>
            ))}
          </div>
        </Card>
        </>
      )}
      {tab === "incidents" && (
        <Card kicker="Incidents" title="From Motor + HMI">
          {!incidents.length && <Empty title="No incidents in this list" body="Open Incidents for replay of similar cases." />}
          {incidents.slice(0, 20).map((row: any, index: number) => (
            <div key={row.id || index} className="border-b border-[#e6edf2] py-2 text-sm">
              {row.title || row.pattern_family || row.incident || JSON.stringify(row).slice(0, 80)}
            </div>
          ))}
        </Card>
      )}
      {tab === "actions" && (
        <Card kicker="Operator actions" title="Recorded actions">
          {!actions.length && <Empty title="No operator actions" body="Actions recorded by the Motor + HMI backend appear here." />}
          {actions.slice(0, 30).map((row: any, index: number) => (
            <div key={row.id || index} className="border-b border-[#e6edf2] py-2 text-sm">
              {row.action_type || row.kind} · {row.operator || "operator"} · {row.detail || row.result || ""}
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
