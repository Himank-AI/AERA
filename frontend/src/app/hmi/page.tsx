"use client";

import Link from "next/link";
import { LiveSignals } from "@/components/LiveSignals";
import { Badge, Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { attentionLabel, fmt, UNITS } from "@/lib/format";
import { useRuntime } from "@/lib/runtime";

export default function HmiPage() {
  const { assessment } = useRuntime();
  const sensors = assessment?.sensors || {};
  const motor = assessment?.motor;
  const risk = assessment?.risk;
  const alarms = assessment?.alarms || [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="kicker">HMI dashboard</div>
          <h1 className="text-2xl font-semibold">Control and monitor</h1>
          <p className="text-sm text-[#5b7388]">Operator interface. Intelligence stays in AERA.</p>
        </div>
        <div className="text-right text-sm">
          <div className="font-semibold">{motor?.code || "MOTOR-01"} · {motor?.status || "—"}</div>
          <div className="text-[#5b7388]">{assessment?.connected ? "CONNECTED" : "DISCONNECTED"}</div>
        </div>
      </div>

      <div>
        <div className="kicker mb-2">Motor status</div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {[
          ["Current", sensors.current, "current"],
          ["Voltage", sensors.voltage, "voltage"],
          ["RPM", sensors.speed, "speed"],
          ["Load", sensors.load, "load"],
          ["Temperature", sensors.temperature, "temperature"],
          ["Vibration", sensors.vibration, "vibration"],
          ["Power", sensors.power, "power"],
        ].map(([label, value, key]) => (
          <div key={String(label)} className="card p-3">
            <div className="kicker">{label}</div>
            <div className="font-mono-aera text-lg">{fmt(value as number)} {UNITS[String(key)]}</div>
          </div>
        ))}
        </div>
      </div>

      <Card kicker="Control panel" title="Operator commands">
          <p className="mb-3 text-xs text-[#5b7388]">Forwards to the Motor + HMI simulator. AERA does not write PLC commands.</p>
          <div className="grid max-w-xl grid-cols-2 gap-2">
            <Button onClick={() => api.start()}>Start</Button>
            <Button variant="ghost" onClick={() => api.stop()}>Stop</Button>
            <Button variant="ghost" onClick={() => api.reset()}>Reset</Button>
            <Button variant="danger" onClick={() => api.stop()}>E-Stop</Button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
            <div>Speed setpoint <div className="font-mono-aera">{fmt(sensors.speed_setpoint || sensors.speed)} RPM</div></div>
            <div>Load setpoint <div className="font-mono-aera">{fmt(sensors.load)}%</div></div>
            <div>Direction <div className="font-semibold">{motor?.direction || "FWD"}</div></div>
            <div>Drive <div className="font-semibold">{motor?.drive_status || "—"}</div></div>
          </div>
        </Card>
        <div className="card flex flex-wrap items-center justify-between gap-3 p-3">
          <div>
            <div className="kicker">AERA</div>
            <div className="text-sm font-semibold">● Monitoring</div>
          </div>
          <div className="text-sm">Attention {attentionLabel(risk?.level)}</div>
          <Badge level={risk?.level}>{risk?.score ?? "—"} / 100</Badge>
          <Link href="/" className="text-xs font-semibold text-[#1d5f8a]">View situation →</Link>
        </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card kicker="Active alarms" title="Operator alarms only">
          {!alarms.length && <p className="text-sm text-[#5b7388]">No active Motor 01 alarms.</p>}
          {alarms.slice(0, 5).map((row, index) => (
            <div key={index} className="border-b border-[#e6edf2] py-2 text-sm">
              {String(row.title || row.alarm_code || "Alarm")}
            </div>
          ))}
          <Link href="/hmi/alarms" className="mt-2 inline-block text-xs text-[#1d5f8a]">All alarms →</Link>
        </Card>
        <LiveSignals />
      </div>
    </div>
  );
}
