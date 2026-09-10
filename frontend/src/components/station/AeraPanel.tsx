"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { attentionTone, cn, fmt } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";
import type { MachineEvent } from "@/lib/types";
import { StationTrends } from "./StationTrends";

type View = "live" | "events" | "history";

export function AeraPanel() {
  const { assessment, applyAssessment } = useRuntime();
  const [view, setView] = useState<View>("live");
  const [message, setMessage] = useState("");
  const [thread, setThread] = useState<Array<{ q: string; a: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

  const copilot = assessment?.copilot_view;
  const rec = assessment?.recommendation || copilot?.recommendation;
  const status = copilot?.status || assessment?.attention || "NORMAL";
  const alert = Boolean(copilot?.alert) || status === "HIGH RISK" || status === "CRITICAL";
  const actionable = Boolean(rec?.actionable) && ["ATTENTION", "HIGH RISK", "CRITICAL"].includes(status);
  const showAlt = rec?.status === "alternative" || rec?.status === "rejected";
  const events = assessment?.events || [];

  useEffect(() => {
    if (view !== "history") return;
    api.history().then((row) => setHistory(row.motor_history || [])).catch(() => undefined);
  }, [view]);

  const ask = async (text: string) => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const response = await api.chat(text);
      setThread((prev) => [...prev, { q: text, a: response.answer || "" }].slice(-6));
    } finally {
      setBusy(false);
      setMessage("");
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    ask(message);
  };

  const act = async (action: string, note = "") => {
    const row = await api.recommend(action, note).catch(() => undefined);
    if (row) applyAssessment(row);
  };

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-[#24303a] bg-[#10161c]">
      <header className="shrink-0 border-b border-[#24303a] px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] tracking-[0.22em] text-[#7d8b96]">AERA</div>
            <div className="text-lg font-semibold">AI INDUSTRIAL COPILOT</div>
          </div>
          <div className="text-right">
            {alert && <div className="aera-alert mb-1">⚠ ALERT</div>}
            <div className={cn("aera-status text-sm", attentionTone(status))}>{status}</div>
          </div>
        </div>
        <div className="mt-3 flex gap-1">
          {(["live", "events", "history"] as const).map((item) => (
            <button key={item} className={cn("tab-btn", view === item && "on")} onClick={() => setView(item)}>
              {item === "live" ? "Live copilot" : item === "events" ? "Event log" : "history"}
            </button>
          ))}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {view === "live" && (
          <div className="space-y-4">
            <Block label="WHAT HAPPENED" body={copilot?.what || "Waiting for live motor data."} />
            <Block label="WHY IT MATTERS" body={copilot?.analysis || ""} />
            <Block label="HISTORY" body={copilot?.history || ""} />
            <Block label="RISK" body={copilot?.risk || ""} />
            {copilot?.cause && (
              <Block label={copilot.cause_certainty || "LIKELY CAUSE"} body={copilot.cause} />
            )}
            <div>
              <div className="kicker">Recommended action</div>
              <div className="mt-1 text-sm font-semibold">{copilot?.action || rec?.primary || "Continue monitoring."}</div>
            </div>

            {showAlt && (
              <div className="rounded border border-[#3a2d0c] bg-[#1a160c] p-3">
                <div className="kicker text-[#f0cf6a]">Alternative action</div>
                <ol className="mt-2 space-y-1 text-sm">
                  {(rec?.alternative || copilot?.alternative || []).map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
                <p className="mt-2 text-xs text-[#7d8b96]">Risk remains {status} until the underlying issue is checked.</p>
              </div>
            )}

            {actionable && rec?.status !== "accepted" && (
              <div className="grid grid-cols-3 gap-2">
                <button className="op-action bg-[#14532d] text-[#b8f5c8]" onClick={() => act("accept")}>Accept</button>
                <button className="op-action" onClick={() => act("reject", "Not possible right now.")}>Not possible</button>
                <button className="op-action" onClick={() => act("alternative")}>Alternative</button>
              </div>
            )}
            {rec?.status === "accepted" && (
              <div className="text-xs uppercase tracking-widest text-[#8ee0a8]">Operator accepted · recorded</div>
            )}

            <div className="grid grid-cols-3 gap-2 text-[11px] text-[#7d8b96]">
              <div>DETECTED <div className="font-mono-aera text-[#d5dee6]">{copilot?.timings?.detected || "—"}</div></div>
              <div>ANALYZED <div className="font-mono-aera text-[#d5dee6]">{copilot?.timings?.analyzed || "—"}</div></div>
              <div>RECOMMENDATION <div className="font-mono-aera text-[#d5dee6]">{copilot?.timings?.recommendation || "—"}</div></div>
            </div>
            {!!copilot?.history_minutes && (
              <div className="text-xs text-[#7d8b96]">Historical average resolution: {fmt(copilot.history_minutes, 0)} min</div>
            )}

            <StationTrends />

            {thread.length > 0 && (
              <div className="space-y-2">
                <div className="kicker">Operator conversation</div>
                {thread.map((item, index) => (
                  <div key={`${item.q}-${index}`} className="rounded border border-[#24303a] bg-[#0c1116] p-3 text-sm">
                    <div className="text-[11px] uppercase tracking-widest text-[#7d8b96]">Operator</div>
                    <div className="mt-1">{item.q}</div>
                    <div className="mt-2 text-[11px] uppercase tracking-widest text-[#7d8b96]">AERA</div>
                    <pre className="mt-1 whitespace-pre-wrap font-sans leading-6">{item.a}</pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {view === "events" && <EventSheet events={events} />}
        {view === "history" && <HistoryList rows={history} />}
      </div>

      {view === "live" && (
        <form onSubmit={onSubmit} className="shrink-0 border-t border-[#24303a] p-3">
          <div className="kicker mb-2">Operator to AERA</div>
          {alert && (
            <div className="mb-2 flex flex-wrap gap-1">
              {["Why is the risk high?", "Has this happened before?", "What should I do?", "I can't reduce the load."].map((item) => (
                <button key={item} type="button" className="rounded border border-[#2a3640] px-2 py-1 text-[10px] uppercase tracking-widest text-[#9aa8b4]" onClick={() => ask(item)}>
                  {item}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="How is the motor? Why? Has this happened before?"
              className="flex-1 rounded border border-[#24303a] bg-[#0c1116] px-3 py-2 text-sm"
            />
            <button type="submit" disabled={busy} className="op-action px-3">{busy ? "…" : "Ask"}</button>
          </div>
        </form>
      )}
    </section>
  );
}

function Block({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div>
      <div className="kicker">{label}</div>
      <p className="mt-1 text-sm leading-6">{body}</p>
    </div>
  );
}

function EventSheet({ events }: { events: MachineEvent[] }) {
  if (!events.length) {
    return <p className="text-sm text-[#7d8b96]">No events recorded yet.</p>;
  }
  return (
    <div>
      <div className="mb-2 text-xs text-[#7d8b96]">Session event / alarm register · append-only</div>
      <div className="log-sheet">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Time</th>
              <th>Event / Alarm Message</th>
              <th>Status</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Condition</th>
              <th>Parameter</th>
              <th>Value</th>
              <th>Equipment</th>
              <th>AERA</th>
              <th>Recommendation</th>
              <th>Operator</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {events.map((row) => (
              <tr key={row.id || `${row.timestamp}-${row.event_type}`}>
                <td>{row.date || (row.timestamp || "").slice(0, 10)}</td>
                <td>{row.clock || row.timestamp?.slice(11, 19)}</td>
                <td className="msg">{row.message || row.event_type.replace(/_/g, " ")}</td>
                <td className={statusClass(row.alarm_status)}>{row.alarm_status || "Recorded"}</td>
                <td>{row.event_kind || row.source || "Event"}</td>
                <td>{row.severity || "NORMAL"}</td>
                <td>{row.condition || "—"}</td>
                <td>{row.parameter || "—"}</td>
                <td>{valueCell(row)}</td>
                <td>{row.equipment || "MOTOR-01"}</td>
                <td>{row.aera_assessment || "—"}</td>
                <td>{row.recommendation || "—"}</td>
                <td>{row.operator_response || "—"}</td>
                <td>{row.outcome || row.context || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function valueCell(row: MachineEvent) {
  if (row.new == null) return "—";
  const prev = row.previous != null ? `${row.previous} → ` : "";
  return `${prev}${row.new}${row.unit ? ` ${row.unit}` : ""}`;
}

function statusClass(status?: string) {
  const key = (status || "").toLowerCase();
  if (key === "active") return "st-active";
  if (key === "return" || key === "resolved") return "st-return";
  if (key === "issued") return "st-issued";
  return "";
}

function HistoryList({ rows }: { rows: any[] }) {
  if (!rows.length) {
    return <p className="text-sm text-[#7d8b96]">Loading historical cases…</p>;
  }
  return (
    <ol className="space-y-3">
      {rows.map((row) => (
        <li key={row.event_number} className="rounded border border-[#24303a] bg-[#0c1116] p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <div className="font-semibold">#{row.event_number} · {(row.timestamp || "").slice(0, 10)}</div>
            <div className={cn("rounded px-2 py-0.5 text-[10px] font-bold", attentionTone(row.severity))}>{row.severity}</div>
          </div>
          <div className="mt-1 text-[#7d8b96]">{row.detected_anomaly || row.description}</div>
          <div className="mt-2 grid grid-cols-3 gap-2 font-mono-aera text-[11px]">
            <div>T {fmt(row.temperature)}°C</div>
            <div>V {fmt(row.vibration)} mm/s</div>
            <div>L {fmt(row.load, 0)}%</div>
          </div>
          <div className="mt-2">{row.operator_action || "No intervention"}</div>
          <div className="text-xs text-[#7d8b96]">{row.outcome} · {row.resolution_minutes || 0} min</div>
        </li>
      ))}
    </ol>
  );
}
