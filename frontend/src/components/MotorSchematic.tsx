"use client";

import { cn, fmt, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

export function MotorSchematic() {
  const { assessment } = useRuntime();
  const running = (assessment?.motor?.status || "").toUpperCase() === "RUNNING" || (assessment?.motor?.drive_status || "") === "RUN";
  const sensors = assessment?.sensors || {};
  const live = assessment?.connected;
  return (
    <div className="card p-4">
      <div className="kicker">Motor visualization</div>
      <div className="mt-4 grid grid-cols-1 items-center gap-4 md:grid-cols-[1.2fr_0.8fr]">
        <svg viewBox="0 0 280 140" className="w-full text-[#12233a]">
          <rect x="8" y="48" width="36" height="44" rx="4" fill="#e8eef3" stroke="#c5d0db" />
          <text x="26" y="74" textAnchor="middle" fontSize="8" fill="#5b7388">LOAD</text>
          <line x1="44" y1="70" x2="86" y2="70" stroke="#9aafbf" strokeWidth="6" />
          <rect x="86" y="36" width="88" height="68" rx="10" fill="#f7fafc" stroke="#12233a" strokeWidth="2" />
          <circle cx="130" cy="70" r="22" fill="none" stroke="#2f9e44" strokeWidth="3" className={cn("motor-rotor", (!running || !live) && "paused")} />
          <circle cx="130" cy="70" r="6" fill="#12233a" />
          <text x="130" y="118" textAnchor="middle" fontSize="9" fill="#5b7388">MOTOR-01</text>
          <line x1="174" y1="70" x2="214" y2="70" stroke="#9aafbf" strokeWidth="6" />
          <rect x="214" y="52" width="50" height="36" rx="4" fill="#e8eef3" stroke="#c5d0db" />
          <text x="239" y="74" textAnchor="middle" fontSize="8" fill="#5b7388">DRIVE</text>
        </svg>
        <div className="space-y-3">
          <div>
            <div className="kicker">State</div>
            <div className="text-2xl font-semibold">{assessment?.motor?.status || "—"}</div>
          </div>
          <div>
            <div className="kicker">RPM</div>
            <div className="font-mono-aera text-xl">{fmt(sensors.speed, 0)} {UNITS.speed}</div>
          </div>
          <div>
            <div className="kicker">Load</div>
            <div className="font-mono-aera text-xl">{fmt(sensors.load)} {UNITS.load}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
