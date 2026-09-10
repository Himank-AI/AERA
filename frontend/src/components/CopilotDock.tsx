"use client";

import { CopilotPanel } from "./CopilotPanel";
import { useRuntime } from "@/lib/runtime";

export function CopilotDock() {
  const { copilotOpen, setCopilotOpen } = useRuntime();
  if (!copilotOpen) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-[#12233a]/20">
      <button className="flex-1" onClick={() => setCopilotOpen(false)} aria-label="Close copilot" />
      <aside className="flex h-full w-full max-w-md flex-col overflow-hidden border-l border-[#d9e1e8] bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-[#d9e1e8] px-4 py-3">
          <div>
            <div className="kicker">AERA Copilot</div>
            <div className="text-sm font-semibold">Ask about this motor</div>
          </div>
          <button className="text-xs uppercase tracking-widest text-[#5b7388]" onClick={() => setCopilotOpen(false)}>
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-4">
          <CopilotPanel compact />
        </div>
      </aside>
    </div>
  );
}
