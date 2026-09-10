import type { Assessment } from "./types";

export const api = {
  state: () => fetch("/api/state", { cache: "no-store" }).then((r) => r.json()) as Promise<Assessment>,
  chat: (message: string, experience_level?: string) =>
    fetch("/api/copilot/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, experience_level }),
    }).then((r) => r.json()),
  whatIf: (body: Record<string, unknown> | string) =>
    fetch("/api/what-if", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(typeof body === "string" ? { message: body } : body),
    }).then((r) => r.json()),
  feedback: (body: Record<string, unknown>) =>
    fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json()),
  outcome: (body: Record<string, unknown>) =>
    fetch("/api/outcomes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json()),
  history: () => fetch("/api/history", { cache: "no-store" }).then((r) => r.json()),
  replay: (n: number) => fetch(`/api/history/replay/${n}`, { cache: "no-store" }).then((r) => r.json()),
  liveReplay: () => fetch("/api/history/replay/live", { cache: "no-store" }).then((r) => r.json()),
  sops: () => fetch("/api/knowledge/sops", { cache: "no-store" }).then((r) => r.json()),
  expert: () => fetch("/api/knowledge/expert", { cache: "no-store" }).then((r) => r.json()),
  parameters: () => fetch("/api/knowledge/parameters", { cache: "no-store" }).then((r) => r.json()),
  learning: () => fetch("/api/learning", { cache: "no-store" }).then((r) => r.json()),
  setExperience: (experience_level: string) =>
    fetch("/api/experience", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ experience_level }) }).then((r) => r.json()),
  addExpert: (body: Record<string, unknown>) =>
    fetch("/api/knowledge/expert", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json()),
  scenario: (scenario: string) =>
    fetch("/api/demo/scenario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario }) }).then((r) => r.json()),
  start: () => fetch("/api/hmi/start", { method: "POST" }).then((r) => r.json()),
  stop: () => fetch("/api/hmi/stop", { method: "POST" }).then((r) => r.json()),
  reset: () => fetch("/api/demo/reset", { method: "POST" }).then((r) => r.json()),
  setParam: (name: string, value: number) =>
    fetch("/api/hmi/set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, value }),
    }).then((r) => r.json()),
  recommend: (action: string, message = "") =>
    fetch("/api/recommendation/respond", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, message }),
    }).then((r) => r.json()),
  events: () => fetch("/api/events", { cache: "no-store" }).then((r) => r.json()),
};

export function wsUrl() {
  if (typeof window === "undefined") return "ws://127.0.0.1:8001/ws/aera";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (window.location.port === "3001") {
    return `${proto}//${window.location.hostname}:8001/ws/aera`;
  }
  return `${proto}//${window.location.host}/ws/aera`;
}
