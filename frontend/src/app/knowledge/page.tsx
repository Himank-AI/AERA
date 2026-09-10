"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Card, Button, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import { useRuntime } from "@/lib/runtime";
import { prettyName } from "@/lib/format";

const SECTIONS = ["Motor Knowledge", "Known Problems", "Troubleshooting", "SOPs", "Expert Experience"];

export default function KnowledgePage() {
  const { search } = useRuntime();
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [sops, setSops] = useState<any[]>([]);
  const [expert, setExpert] = useState<any[]>([]);
  const [open, setOpen] = useState("vibration");
  const [section, setSection] = useState("Motor Knowledge");

  useEffect(() => {
    api.parameters().then(setParameters).catch(() => undefined);
    api.sops().then(setSops).catch(() => undefined);
    api.expert().then(setExpert).catch(() => undefined);
  }, []);

  const q = search.toLowerCase();
  const current = parameters[open];
  const filteredSops = useMemo(() => sops.filter((sop) => !q || JSON.stringify(sop).toLowerCase().includes(q)), [sops, q]);
  const filteredExpert = useMemo(() => expert.filter((row) => !q || JSON.stringify(row).toLowerCase().includes(q)), [expert, q]);

  const addExpert = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await api.addExpert({
      problem: data.get("problem"),
      symptoms: String(data.get("symptoms") || "").split(",").map((s) => s.trim()),
      cause: data.get("cause"),
      solution: data.get("solution"),
      warnings: String(data.get("warnings") || "").split(",").map((s) => s.trim()),
      outcome: data.get("outcome"),
      notes: data.get("notes"),
      source: data.get("source") || "Operator",
      pattern_family: data.get("pattern_family"),
    });
    setExpert(await api.expert());
    event.currentTarget.reset();
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">AERA · Knowledge</div>
        <h1 className="text-2xl font-semibold">Motor knowledge system</h1>
        <p className="text-sm text-[#5b7388]">Searchable industrial knowledge for Motor 01. Not generated live telemetry.</p>
      </div>
      <div className="flex flex-wrap gap-1">
        {SECTIONS.map((item) => (
          <button key={item} onClick={() => setSection(item)} className={`rounded-full px-3 py-1 text-xs ${section === item ? "bg-[#12233a] text-white" : "border border-[#d9e1e8]"}`}>
            {item}
          </button>
        ))}
      </div>

      {(section === "Motor Knowledge" || section === "Troubleshooting") && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <Card kicker="Topics" title="Motor parameters">
            <div className="flex flex-wrap gap-1">
              {Object.keys(parameters).map((key) => (
                <button key={key} className={`rounded-md border px-2 py-1 text-xs ${open === key ? "border-[#2f9e44] bg-[#e8f6eb]" : "border-[#d9e1e8]"}`} onClick={() => setOpen(key)}>
                  {prettyName(key)}
                </button>
              ))}
            </div>
          </Card>
          <Card kicker={current?.name || "Topic"} title={section === "Troubleshooting" ? "Recommended checks" : current?.meaning}>
            {current ? (
              <div className="space-y-3 text-sm">
                {section === "Motor Knowledge" ? (
                  <>
                    <div><span className="text-[#5b7388]">Normal:</span> {current.normal_behaviour}</div>
                    <div><span className="text-[#5b7388]">Warning:</span> {current.warning_behaviour}</div>
                    <div><span className="text-[#5b7388]">Critical:</span> {current.critical_behaviour}</div>
                  </>
                ) : (
                  <>
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-[#5b7388]">Symptoms</div>
                      {current.warning_behaviour}
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-[#5b7388]">Possible causes</div>
                      <ul className="list-disc pl-4">{(current.possible_causes || []).map((item: string) => <li key={item}>{item}</li>)}</ul>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-[#5b7388]">Recommended checks</div>
                      <ol className="list-decimal pl-4">{(current.recommended_checks || []).map((item: string) => <li key={item}>{item}</li>)}</ol>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <Empty title="Select a topic" body="Choose a motor parameter to see knowledge and checks." />
            )}
          </Card>
        </div>
      )}

      {(section === "SOPs") && (
        <Card kicker="SOPs" title="Procedures">
          {!filteredSops.length && <Empty title="No matching SOP" body="No stored procedure matched the current search." />}
          {filteredSops.map((sop) => (
            <div key={sop.code} className="mb-3 border-b border-[#e6edf2] pb-3 text-sm">
              <div className="font-semibold">{sop.code} · {sop.title}</div>
              <div className="text-[#5b7388]">{sop.purpose}</div>
              <ol className="mt-1 list-decimal pl-4">
                {(sop.steps || []).map((step: string) => <li key={step}>{step}</li>)}
              </ol>
            </div>
          ))}
        </Card>
      )}

      {(section === "Known Problems" || section === "Expert Experience") && (
        <Card kicker="Experience library" title="Plant-specific knowledge transfer">
          <p className="mb-3 text-xs uppercase tracking-widest text-[#5b7388]">Distinguished from generic generated advice</p>
          {!filteredExpert.length && <Empty title="No expert notes" body="Stored operator and engineer experience will appear here." />}
          {filteredExpert.map((row) => (
            <div key={row.id} className="mb-3 rounded-lg border border-[#d9e1e8] p-3 text-sm">
              <div className="kicker">{row.id}</div>
              <div className="mt-1"><span className="text-[#5b7388]">Problem:</span> {row.problem}</div>
              <div><span className="text-[#5b7388]">Symptoms:</span> {(row.symptoms || []).join(", ")}</div>
              <div><span className="text-[#5b7388]">Diagnosis:</span> {row.cause}</div>
              <div><span className="text-[#5b7388]">Solution:</span> {row.solution}</div>
              <div><span className="text-[#5b7388]">Outcome:</span> {row.outcome}</div>
              <div className="mt-1 text-[#5b7388]">Source: {row.source}</div>
            </div>
          ))}
          {section === "Expert Experience" && (
            <form onSubmit={addExpert} className="mt-4 grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
              <input name="problem" placeholder="Problem" className="rounded-md border border-[#d9e1e8] px-2 py-1" required />
              <input name="pattern_family" placeholder="Pattern family" className="rounded-md border border-[#d9e1e8] px-2 py-1" />
              <input name="symptoms" placeholder="Symptoms" className="rounded-md border border-[#d9e1e8] px-2 py-1" />
              <input name="cause" placeholder="Diagnosis" className="rounded-md border border-[#d9e1e8] px-2 py-1" />
              <input name="solution" placeholder="Solution" className="rounded-md border border-[#d9e1e8] px-2 py-1" />
              <input name="source" placeholder="Source" className="rounded-md border border-[#d9e1e8] px-2 py-1" />
              <input name="outcome" placeholder="Outcome" className="col-span-full rounded-md border border-[#d9e1e8] px-2 py-1" />
              <Button type="submit">Add expert note</Button>
            </form>
          )}
        </Card>
      )}
    </div>
  );
}
