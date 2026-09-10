export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function fmt(value: number | undefined | null, digits = 1) {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function riskClass(level?: string) {
  const key = (level || "UNKNOWN").toUpperCase();
  return `risk-${key}`;
}

export const UNITS: Record<string, string> = {
  temperature: "°C",
  current: "A",
  voltage: "V",
  vibration: "mm/s",
  speed: "RPM",
  load: "%",
  power: "kW",
  torque: "Nm",
  frequency: "Hz",
  energy: "kWh",
  runtime: "h",
  speed_setpoint: "RPM",
};

export type AttentionLabel = "NORMAL" | "ATTENTION" | "HIGH RISK" | "CRITICAL" | "UNKNOWN";

export function attentionLabel(level?: string): AttentionLabel | "ALERT" | "RESOLVED" {
  switch ((level || "").toUpperCase()) {
    case "NORMAL":
    case "STABLE":
      return "NORMAL";
    case "RESOLVED":
      return "NORMAL";
    case "MONITOR":
    case "LOW":
    case "MEDIUM":
    case "ATTENTION":
      return "ATTENTION";
    case "HIGH":
    case "HIGH RISK":
    case "ALERT":
      return "HIGH RISK";
    case "CRITICAL":
      return "CRITICAL";
    default:
      return "UNKNOWN";
  }
}

export function attentionTone(level?: string) {
  const raw = (level || "").toUpperCase();
  if (raw === "RESOLVED") return "tone-stable";
  if (raw === "ALERT" || raw === "ALARM") return "tone-critical";
  const label = attentionLabel(level);
  return {
    NORMAL: "tone-stable",
    ATTENTION: "tone-attention",
    "HIGH RISK": "tone-high",
    CRITICAL: "tone-critical",
    UNKNOWN: "tone-unknown",
  }[label];
}

export function secondsAgo(iso?: string) {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return Math.max(0, Math.round((Date.now() - then) / 1000));
}

export function factorLabel(key: string) {
  const map: Record<string, string> = {
    severity: "Signal deviation",
    rate_of_change: "Parameter trend",
    combined_pattern: "Combined motor pattern",
    historical_failure: "Historical similarity",
    isolation_forest: "Statistical unusualness",
    active_alarm: "Active motor alarm",
    operating_context: "Operating context",
    temperature: "Temperature",
    vibration: "Vibration trend",
  };
  return map[key] || key.replace(/_/g, " ");
}

export function prettyName(key: string) {
  const map: Record<string, string> = {
    speed: "Speed",
    load: "Load",
    temperature: "Temperature",
    vibration: "Vibration",
    current: "Current",
    voltage: "Voltage",
    torque: "Torque",
    power: "Power",
    frequency: "Frequency",
    energy: "Energy",
    runtime: "Runtime",
    speed_setpoint: "Speed setpoint",
    start_cycles: "Start cycles",
  };
  return map[key] || key.replace(/_/g, " ");
}

export function connectionLabel(aeraConnected: boolean, motorConnected?: boolean) {
  if (!aeraConnected) return { label: "RECONNECTING", tone: "wait" as const };
  if (!motorConnected) return { label: "DISCONNECTED", tone: "off" as const };
  return { label: "LIVE", tone: "" as const };
}
