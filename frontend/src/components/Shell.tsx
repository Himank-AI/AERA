"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CopilotDock } from "@/components/CopilotDock";
import { RuntimeProvider, useRuntime } from "@/lib/runtime";
import { attentionLabel, attentionTone, cn, connectionLabel, fmt } from "@/lib/format";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <RuntimeProvider>
      <Frame>{children}</Frame>
    </RuntimeProvider>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  const { assessment, connected } = useRuntime();
  const pathname = usePathname();
  const station = pathname === "/";
  const motor = assessment?.motor;
  const sensors = assessment?.sensors || {};
  const live = connected && assessment?.connected;
  const link = connectionLabel(connected, assessment?.connected);
  const status = assessment?.attention || attentionLabel(assessment?.risk?.level);

  return (
    <div className="flex h-dvh max-h-dvh flex-col overflow-hidden bg-[#07090c] text-[#d5dee6]">
      <header className="flex shrink-0 items-center gap-4 border-b border-[#24303a] bg-[#0c1116] px-4 py-2">
        <Link href="/" className="leading-tight">
          <div className="text-[10px] tracking-[0.22em] text-[#7d8b96]">AERA</div>
          <div className="text-sm font-semibold">AI Industrial Copilot</div>
        </Link>
        <div className="h-6 w-px bg-[#24303a]" />
        <div className="whitespace-nowrap text-sm">
          <span className="font-semibold">{motor?.code || "MOTOR-01"}</span>
          <span className="ml-2 text-[#7d8b96]">{motor?.status || "—"}</span>
        </div>
        <div className="flex items-center gap-2 whitespace-nowrap text-xs">
          <span className={cn("live-dot", link.tone)} />
          {live ? "LIVE" : link.label}
        </div>
        <div className="hidden whitespace-nowrap font-mono-aera text-xs text-[#7d8b96] md:block">{fmt(sensors.load, 0)}% load</div>
        <div className={cn("ml-auto rounded px-2 py-1 text-[11px] font-bold tracking-widest", attentionTone(status))}>
          {status}
        </div>
        {!station && (
          <Link href="/" className="rounded border border-[#24303a] px-2 py-1 text-[11px] uppercase tracking-widest">
            Station
          </Link>
        )}
      </header>
      <main className={cn("min-h-0 flex-1", station ? "overflow-hidden" : "overflow-y-auto p-4")}>{children}</main>
      {!station && <CopilotDock />}
    </div>
  );
}

export { Card } from "./ui";
export { Overlay } from "./ui";
export function Kpi({ label, value, unit }: { label: string; value?: number | string; unit?: string; trend?: number }) {
  return (
    <div className="card p-3">
      <div className="kicker">{label}</div>
      <div className="mt-1 font-mono-aera text-xl">
        {typeof value === "number" ? fmt(value) : value || "—"} <span className="text-sm text-[#7d8b96]">{unit}</span>
      </div>
    </div>
  );
}
