"use client";

import { AeraPanel } from "@/components/station/AeraPanel";
import { IndustrialHmi } from "@/components/station/IndustrialHmi";
import { IndustrialMotor } from "@/components/station/IndustrialMotor";

export default function OperatorStation() {
  return (
    <div className="station">
      <div className="station-left">
        <IndustrialMotor />
        <IndustrialHmi />
      </div>
      <div className="station-right">
        <AeraPanel />
      </div>
    </div>
  );
}
