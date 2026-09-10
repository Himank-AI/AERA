"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { useRuntime } from "@/lib/runtime";
import { Button, Card, Chip } from "./ui";

const PROMPTS = [
  "What is happening?",
  "Why was this flagged?",
  "Has this happened before?",
  "What should I check?",
  "Can I continue?",
  "What did the operator do last time?",
  "What could happen next?",
];

export function CopilotPanel({ compact = false }: { compact?: boolean }) {
  const { assessment, experience } = useRuntime();
  const [message, setMessage] = useState("");
  const [log, setLog] = useState<Array<{ q: string; a: string; sections?: Record<string, string>; sim?: boolean }>>([]);
  const [busy, setBusy] = useState(false);

  const ask = async (text: string) => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const response = await api.chat(text, experience);
      setLog((prev) => [{ q: text, a: response.answer, sections: response.sections, sim: response.simulation }, ...prev].slice(0, 6));
    } finally {
      setBusy(false);
      setMessage("");
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    ask(message);
  };

  const body = (
    <>
      <div className="flex flex-wrap gap-1">
        {PROMPTS.map((item) => (
          <button key={item} className="rounded-full border border-[#d9e1e8] px-2 py-1 text-[11px] hover:border-[#2f9e44]" onClick={() => ask(item)}>
            {item}
          </button>
        ))}
      </div>
      <form onSubmit={onSubmit} className="mt-3 flex gap-2">
        <input value={message} onChange={(e) => setMessage(e.target.value)} className="flex-1 rounded-md border border-[#d9e1e8] px-3 py-2 text-sm" placeholder="Ask about Motor 01…" />
        <Button type="submit" disabled={busy}>{busy ? "…" : "Ask"}</Button>
      </form>
      <div className={compact ? "mt-3 space-y-3" : "mt-3 max-h-[28rem] space-y-3 overflow-auto"}>
        {log.map((item, index) => (
          <div key={index} className="rounded-lg border border-[#e6edf2] bg-[#f8fafb] p-3 text-sm">
            {item.sim && <div className="mb-1 text-[10px] uppercase tracking-widest text-[#d45a16]">Simulation / estimate</div>}
            <div className="text-[11px] uppercase tracking-widest text-[#5b7388]">{item.q}</div>
            {item.sections && Object.keys(item.sections).length ? (
              <dl className="mt-2 space-y-2">
                {Object.entries(item.sections).map(([key, value]) =>
                  value ? (
                    <div key={key}>
                      <dt className="text-[10px] uppercase tracking-widest text-[#5b7388]">{key}</dt>
                      <dd>{value}</dd>
                    </div>
                  ) : null,
                )}
              </dl>
            ) : (
              <pre className="mt-2 whitespace-pre-wrap font-sans">{item.a}</pre>
            )}
            <div className="mt-2 flex flex-wrap gap-1">
              <Chip>Historical match</Chip>
              <Chip>Load context</Chip>
              <Chip>Trend analysis</Chip>
              {assessment?.similar?.matches?.[0] && <Chip>Previous incident</Chip>}
            </div>
          </div>
        ))}
        {!log.length && (
          <p className="text-sm text-[#5b7388]">
            What would you like to know? AERA already has live Motor 01 context.
          </p>
        )}
      </div>
    </>
  );

  if (compact) return body;
  return (
    <Card kicker="AERA Copilot" title="Ask about this motor">
      {body}
    </Card>
  );
}
