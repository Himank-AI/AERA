"use client";

import { LiveSignals } from "@/components/LiveSignals";
import { useRuntime } from "@/lib/runtime";

export default function HmiTrendsPage() {
  const { assessment } = useRuntime();
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">HMI · Trends</div>
        <h1 className="text-2xl font-semibold">Live Motor 01 trends</h1>
        <p className="text-sm text-[#5b7388]">{assessment?.motor?.status || "—"} · click a signal to expand</p>
      </div>
      <LiveSignals />
    </div>
  );
}
