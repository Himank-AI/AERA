"use client";

import Link from "next/link";
import { Card, Empty, Badge } from "@/components/ui";
import { useRuntime } from "@/lib/runtime";
import { attentionLabel } from "@/lib/format";

export default function HmiAlarmsPage() {
  const { assessment } = useRuntime();
  const alarms = assessment?.alarms || [];
  const risk = assessment?.risk;
  return (
    <div className="space-y-4">
      <div>
        <div className="kicker">HMI · Alarms</div>
        <h1 className="text-2xl font-semibold">Active alarms</h1>
      </div>
      <Card kicker="Active alarms" title="Operator alarms">
        {!alarms.length && <Empty title="No active alarms" body="No active Motor 01 alarms are being reported by the motor backend." />}
        {alarms.map((row, index) => (
          <div key={index} className="border-b border-[#e6edf2] py-2 text-sm">
            <div className="font-semibold">{String(row.title || row.alarm_code || "Alarm")}</div>
            <div className="text-[#5b7388]">{String(row.status || "")} · {String(row.priority || "")}</div>
          </div>
        ))}
      </Card>
      <div className="card flex flex-wrap items-center justify-between gap-3 p-3">
        <div>
          <div className="kicker">AERA</div>
          <div className="text-sm">{attentionLabel(risk?.level)} · {risk?.score ?? "—"} / 100</div>
        </div>
        <Link href="/" className="text-xs font-semibold text-[#1d5f8a]">View situation →</Link>
        <Badge level={risk?.level}>{risk?.level || "NORMAL"}</Badge>
      </div>
    </div>
  );
}
