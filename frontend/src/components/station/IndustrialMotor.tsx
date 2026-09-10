"use client";

import { cn, fmt } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

export function IndustrialMotor() {
  const { assessment } = useRuntime();
  const mode = (assessment?.motor?.status || "STOPPED").toUpperCase();
  const health = String(assessment?.motor?.health_status || "NORMAL").toUpperCase();
  const running = mode === "RUNNING" || mode === "STARTING";
  const stopping = mode === "STOPPING";
  const alarm = health === "ALARM" || Boolean(assessment?.motor?.fault_state);
  const sensors = assessment?.sensors || {};
  const rpm = sensors.speed || 0;
  const vib = sensors.vibration || 0;
  const spin = running && rpm > 40 ? `${Math.max(0.35, 1800 / Math.max(rpm, 200))}s` : "2.8s";
  const lamp = alarm ? "#e24a4a" : health === "ANOMALY" ? "#d4a017" : running ? "#3ecf6a" : stopping ? "#d4a017" : "#5c6b76";
  const shake = running && vib >= 6.5;

  return (
    <div className={cn("motor-stage flex min-h-0 flex-1 flex-col p-3", shake && "motor-shake")}>
      <div className="flex items-center justify-between">
        <div>
          <div className="kicker">Industrial motor</div>
          <div className="text-sm font-semibold">MOTOR-01 · Drive end</div>
        </div>
        <div className="flex items-center gap-2 text-xs font-semibold">
          <span className="status-lamp" style={{ background: lamp, color: lamp }} />
          {alarm ? "ALARM" : health === "ANOMALY" ? "ANOMALY" : mode}
        </div>
      </div>

      <svg viewBox="0 0 520 210" className="mx-auto mt-1 w-full max-w-[560px] flex-1" style={{ ["--spin" as string]: spin }}>
        <defs>
          <linearGradient id="iron" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#3a4650" />
            <stop offset="45%" stopColor="#1c262e" />
            <stop offset="100%" stopColor="#12181e" />
          </linearGradient>
          <linearGradient id="fin" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#2a343c" />
            <stop offset="50%" stopColor="#4a5864" />
            <stop offset="100%" stopColor="#1b242c" />
          </linearGradient>
        </defs>

        <rect x="20" y="168" width="480" height="10" rx="2" fill="#1a2228" />
        <rect x="108" y="158" width="18" height="18" fill="#2a343c" />
        <rect x="318" y="158" width="18" height="18" fill="#2a343c" />

        {/* Fan cowl */}
        <rect x="86" y="48" width="44" height="110" rx="8" fill="url(#iron)" stroke="#4a5864" />
        <circle cx="108" cy="103" r="22" fill="#0d1216" stroke="#5a6a76" />
        <g className={cn("fan-spin", !running && "paused")}>
          <path d="M108 103 L108 84 L116 90 Z" fill="#8aa0b0" />
          <path d="M108 103 L127 103 L121 111 Z" fill="#6a8090" />
          <path d="M108 103 L108 122 L100 116 Z" fill="#8aa0b0" />
          <path d="M108 103 L89 103 L95 95 Z" fill="#6a8090" />
        </g>

        {/* Frame with cooling fins */}
        <rect x="128" y="46" width="210" height="114" rx="6" fill="url(#iron)" stroke="#6a7a86" />
        {Array.from({ length: 14 }).map((_, i) => (
          <rect key={i} x={138 + i * 13} y="52" width="7" height="102" rx="1" fill="url(#fin)" opacity="0.9" />
        ))}
        <rect x="186" y="38" width="78" height="28" rx="3" fill="#1b242c" stroke="#6a7a86" />
        <text x="225" y="56" textAnchor="middle" fontSize="8" fill="#9aa8b4">TERM BOX</text>

        {/* Shaft + coupling */}
        <rect x="338" y="96" width="86" height="14" rx="2" fill="#c5d0d8" />
        <g className={cn("shaft-spin", !running && "paused")}>
          <circle cx="378" cy="103" r="16" fill="none" stroke="#d4a017" strokeWidth="3" strokeDasharray="8 6" />
          <circle cx="412" cy="103" r="16" fill="none" stroke="#8aa0b0" strokeWidth="3" strokeDasharray="8 6" />
        </g>
        <circle cx="378" cy="103" r="5" fill="#1a2228" />
        <circle cx="412" cy="103" r="5" fill="#1a2228" />

        {/* Driven load */}
        <rect x="424" y="70" width="70" height="66" rx="4" fill="#1b242c" stroke="#5a6a76" />
        <text x="459" y="98" textAnchor="middle" fontSize="9" fill="#9aa8b4">LOAD</text>
        <text x="459" y="114" textAnchor="middle" fontSize="10" fill="#d5dee6">{fmt(sensors.load, 0)}%</text>

        <rect x="168" y="132" width="86" height="18" rx="2" fill="#0d1216" stroke="#5a6a76" />
        <text x="211" y="144" textAnchor="middle" fontSize="8" fill="#c5d0d8">MOTOR-01</text>
      </svg>

      <div className="mt-auto grid grid-cols-4 gap-2 text-center">
        <div>
          <div className="kicker">RPM</div>
          <div className="font-mono-aera text-lg">{fmt(rpm, 0)}</div>
        </div>
        <div>
          <div className="kicker">Temp</div>
          <div className="font-mono-aera text-lg">{fmt(sensors.temperature)}°</div>
        </div>
        <div>
          <div className="kicker">Vib</div>
          <div className={cn("font-mono-aera text-lg", vib >= 6 ? "text-[#ffb089]" : "")}>{fmt(sensors.vibration)}</div>
        </div>
        <div>
          <div className="kicker">Current</div>
          <div className="font-mono-aera text-lg">{fmt(sensors.current)}A</div>
        </div>
      </div>
    </div>
  );
}
