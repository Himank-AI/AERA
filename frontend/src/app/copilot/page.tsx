"use client";

import { CopilotPanel } from "@/components/CopilotPanel";
import { ObserveChain } from "@/components/Intelligence";
import { useRuntime } from "@/lib/runtime";

export default function CopilotPage() {
  const { advanced, setCopilotOpen } = useRuntime();
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">AERA Copilot</div>
        <h1 className="text-2xl font-semibold">Ask about this motor</h1>
        <p className="text-sm text-[#5b7388]">AERA already has live Motor 01 context. You do not need to describe the operating point.</p>
      </div>
      <CopilotPanel />
      <button className="text-xs text-[#1d5f8a]" onClick={() => setCopilotOpen(true)}>Open as side panel</button>
      {advanced && <ObserveChain />}
    </div>
  );
}
