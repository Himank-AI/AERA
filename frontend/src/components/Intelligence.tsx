"use client";

import Link from "next/link";
import { attentionLabel, cn } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";
import { Badge, Button, Card, Empty } from "./ui";

export function AttentionPanel({ onEvidence }: { onEvidence?: () => void }) {
  const { assessment } = useRuntime();
  const risk = assessment?.risk;
  const deviations = (assessment?.deviations || []).filter((row) => row.unusual || Math.abs(row.percent_change) >= 8);
  const top = [...deviations].sort((a, b) => Math.abs(b.percent_change) - Math.abs(a.percent_change))[0];
  const similar = assessment?.similar;
  const quiet = !risk?.level || ["NORMAL", "MONITOR"].includes(risk.level);

  if (quiet && !top) {
    return (
      <Card kicker="What deserves attention?" title="No active concerns">
        <Empty
          title="AERA is continuously monitoring"
          body="No abnormal situation currently requires your attention. Quietly watched values stay in the monitor list instead of becoming alarms."
        />
      </Card>
    );
  }

  return (
    <Card kicker="What deserves attention?" title={top ? `${top.title} trending` : attentionLabel(risk?.level)}>
      {top && (
        <div className="mb-3">
          <div className="font-mono-aera text-2xl">
            {top.value.toFixed(1)} {top.unit}
          </div>
          {Math.abs(top.percent_change) >= 1 && (
          <div className={cn("text-sm", top.percent_change > 0 ? "text-[#d45a16]" : "text-[#1b7a38]")}>
            {top.percent_change > 0 ? "↑" : "↓"} {Math.abs(top.percent_change).toFixed(0)}% vs recent pattern
          </div>
          )}
        </div>
      )}
      <p className="text-sm">{top?.note || risk?.reason}</p>
      {similar?.summary && (
        <div className="mt-3 rounded-lg border border-[#d7e6f0] bg-[#f4f8fb] p-3 text-sm text-[#1d5f8a]">
          <div className="text-[10px] uppercase tracking-widest">Why AERA flagged it</div>
          {similar.summary}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <Badge level={risk?.level}>{risk?.level}</Badge>
        <span className="text-[#5b7388]">{similar?.count || 0} similar incidents</span>
      </div>
      <p className="mt-3 text-sm">{risk?.recommended_response}</p>
      <div className="mt-4">
        <Button onClick={onEvidence}>View evidence →</Button>
      </div>
    </Card>
  );
}

export function QuietlyMonitored() {
  const { assessment } = useRuntime();
  const high = ["HIGH", "CRITICAL"].includes(assessment?.risk?.level || "");
  if (high) return null;
  const quiet = (assessment?.deviations || []).filter((row) => !row.unusual && Math.abs(row.delta) > 0.5);
  const points = assessment?.why_not_flagged?.points || [];
  const temp = (assessment?.deviations || []).find((row) => row.name === "temperature");
  const watch = quiet[0] || temp;
  return (
    <Card kicker="Quietly monitored" title="AERA did not raise an alert">
      {watch ? (
        <div className="mb-2 font-mono-aera text-lg">
          {watch.title} {watch.value.toFixed(1)} {watch.unit}
        </div>
      ) : (
        <div className="mb-2 text-sm font-semibold">No alert-worthy deviation</div>
      )}
      <p className="text-sm text-[#5b7388]">
        {points[0] || watch?.note || "AERA does not alert on every elevated-looking value. It decides what matters for this operating condition."}
      </p>
      <div className="mt-3">
        <Badge level="MONITOR">Monitoring</Badge>
      </div>
    </Card>
  );
}

export function EvidencePanel() {
  const { assessment, advanced } = useRuntime();
  const top = [...(assessment?.deviations || [])].sort((a, b) => Math.abs(b.percent_change) - Math.abs(a.percent_change))[0];
  const match = assessment?.similar?.matches?.[0];
  const load = assessment?.deviations?.find((row) => row.name === "load");
  const observed = top
    ? `${top.title} ${top.percent_change > 0 ? "increased" : "changed"} ${Math.abs(top.percent_change).toFixed(0)}%`
    : assessment?.situation?.what || assessment?.narrative || "Live Motor 01 sample received.";
  const context = load
    ? `Load ${Math.abs(load.percent_change) >= 4 ? "changed with the condition" : "remained relatively stable"} (${load.value.toFixed(0)}%).`
    : assessment?.situation?.why || "Interpreted against the current operating point.";
  return (
    <div className="space-y-3 text-sm">
      <div>
        <div className="kicker">Observed</div>
        <div>{observed}</div>
      </div>
      <div>
        <div className="kicker">Context</div>
        <div>{context}</div>
      </div>
      <div>
        <div className="kicker">Historical match</div>
        <div>{match ? `${match.similarity}%` : "No close incident match"}</div>
      </div>
      {match && (
        <div>
          <div className="kicker">Previous incident</div>
          <div>INC-{match.event_number} · {match.root_cause}</div>
        </div>
      )}
      <div>
        <div className="kicker">Risk</div>
        <Badge level={assessment?.risk?.level}>{assessment?.risk?.level || "—"} · {assessment?.risk?.score ?? "—"} / 100</Badge>
      </div>
      {advanced && (
        <details className="text-xs text-[#5b7388]">
          <summary className="cursor-pointer">Technical details</summary>
          <div className="mt-2 space-y-1">
            {(assessment?.why_flagged?.points || []).map((item) => <div key={item}>{item}</div>)}
          </div>
        </details>
      )}
    </div>
  );
}

export function RecommendationCard() {
  const { assessment } = useRuntime();
  const checks = assessment?.guidance?.checks || [];
  const sop = assessment?.guidance?.sop;
  if (!checks.length) {
    return (
      <Card kicker="Recommended next step" title="Continue normal operation">
        <p className="text-sm text-[#5b7388]">AERA recommends. The operator decides. No motor command is sent.</p>
      </Card>
    );
  }
  return (
    <Card kicker="Recommended next step">
      <ol className="space-y-3">
        {checks.slice(0, 3).map((row) => (
          <li key={row.step} className="flex gap-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#12233a] text-xs text-white">{row.step}</span>
            <div>
              <div className="text-sm font-semibold">{row.action}</div>
              <div className="text-xs text-[#5b7388]">{row.reason}</div>
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link className="rounded-md border border-[#d9e1e8] px-3 py-1.5 text-xs hover:bg-[#f4f6f8]" href="/hmi/trends">View trend</Link>
        <Link className="rounded-md border border-[#d9e1e8] px-3 py-1.5 text-xs hover:bg-[#f4f6f8]" href="/incidents">View incident</Link>
        {sop && <Link className="rounded-md border border-[#d9e1e8] px-3 py-1.5 text-xs hover:bg-[#f4f6f8]" href="/knowledge">View SOP</Link>}
      </div>
      <p className="mt-3 text-xs text-[#5b7388]">AERA recommends. The operator decides.</p>
    </Card>
  );
}

export function HistoricalMatchCard() {
  const { assessment } = useRuntime();
  const match = assessment?.similar?.matches?.[0];
  const count = assessment?.similar?.count || 0;
  if (!match) {
    return (
      <Card kicker="Historical context" title="No similar situations found">
        <p className="text-sm text-[#5b7388]">Current Motor 01 behaviour does not closely match a stored incident.</p>
      </Card>
    );
  }
  return (
    <Card kicker="Historical context" title={`${count} similar situation${count === 1 ? "" : "s"} found`}>
      <div className="kicker">Most relevant</div>
      <div className="text-sm font-semibold">INC-{match.event_number} · {match.root_cause}</div>
      <div className="mt-2 text-sm">Similarity {match.similarity}%</div>
      <p className="mt-2 text-sm text-[#5b7388]">{match.outcome || match.operator_action}</p>
      <Link href={`/incidents?event=${match.event_number}`} className="mt-4 inline-flex rounded-md bg-[#12233a] px-3 py-1.5 text-xs text-white">
        View incident →
      </Link>
    </Card>
  );
}

export function EventTimeline() {
  const { assessment } = useRuntime();
  const items = assessment?.timeline || [];
  return (
    <Card kicker="Event timeline" title="What AERA observed">
      {!items.length && <p className="text-sm text-[#5b7388]">No situation transitions yet on this live session.</p>}
      <ol className="space-y-3">
        {items.slice(-8).map((item, index) => (
          <li key={`${item.time}-${index}`} className="border-l-2 border-[#2f9e44] pl-3">
            <div className="font-mono-aera text-[11px] text-[#5b7388]">{item.time?.slice(11, 19) || item.time}</div>
            <div className="text-sm font-semibold">{item.label}</div>
            <div className="text-xs text-[#5b7388]">{item.detail}</div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export function ObserveChain() {
  const { assessment } = useRuntime();
  const risk = assessment?.risk;
  const similar = assessment?.similar;
  const steps = [
    { label: "Observed", text: assessment?.narrative || "Waiting for Motor 01." },
    { label: "Understood", text: assessment?.situation?.what || "No grouped pattern." },
    { label: "Compared", text: similar?.summary || "No historical match required." },
    { label: "Assessed", text: `${attentionLabel(risk?.level)} · ${risk?.score ?? "—"}/100` },
    { label: "Explained", text: risk?.reason || "Within expected behaviour." },
    { label: "Guided", text: risk?.recommended_response || "Continue monitoring." },
  ];
  return (
    <Card kicker="AERA loop" title="Observe → understand → compare → assess → explain → guide">
      <div className="grid gap-2">
        {steps.map((step) => (
          <div key={step.label} className="grid grid-cols-[96px_1fr] gap-2 text-sm">
            <div className="text-[11px] uppercase tracking-widest text-[#5b7388]">{step.label}</div>
            <div>{step.text}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function GroupedSituation() {
  const { assessment } = useRuntime();
  const alarms = assessment?.alarms || [];
  const situation = assessment?.situation;
  if (!alarms.length && (!situation || situation.title === "STABLE OPERATION")) {
    return (
      <Card kicker="Notifications" title="No grouped attention">
        <Empty title="No notification spam" body="Related signals are grouped. Nothing currently requires an operator interrupt." />
      </Card>
    );
  }
  return (
    <Card kicker="Grouped attention" title={situation?.title || "Related signals"}>
      <p className="text-sm">{situation?.what || assessment?.narrative}</p>
      <p className="mt-2 text-sm text-[#5b7388]">{alarms.length} related signals detected from the Motor + HMI backend.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge level={assessment?.risk?.level}>{assessment?.risk?.level || "MONITOR"}</Badge>
        <Link href="/" className="rounded-md border border-[#d9e1e8] px-3 py-1.5 text-xs">View situation</Link>
      </div>
    </Card>
  );
}
