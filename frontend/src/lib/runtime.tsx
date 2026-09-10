"use client";

import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { api, wsUrl } from "./api";
import type { Assessment } from "./types";

interface Runtime {
  assessment: Assessment | null;
  applyAssessment: (row: Assessment | null | undefined) => void;
  connected: boolean;
  experience: string;
  setExperience: (value: string) => void;
  advanced: boolean;
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
  search: string;
  setSearch: (value: string) => void;
  panel: string | null;
  setPanel: (value: string | null) => void;
  lastSeen: number;
  copilotOpen: boolean;
  setCopilotOpen: (value: boolean) => void;
}

const Ctx = createContext<Runtime | null>(null);

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [connected, setConnected] = useState(false);
  const [experience, setExperienceState] = useState("NEW");
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [panel, setPanel] = useState<string | null>(null);
  const [lastSeen, setLastSeen] = useState(0);
  const [copilotOpen, setCopilotOpen] = useState(false);

  useEffect(() => {
    api.state().then((row) => {
      setAssessment(row);
      setLastSeen(Date.now());
    }).catch(() => undefined);
    let closed = false;
    let retry: number | undefined;
    let socket: WebSocket | null = null;
    const connect = () => {
      if (closed) return;
      socket = new WebSocket(wsUrl());
      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry = window.setTimeout(connect, 2000);
      };
      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "assessment") {
          setAssessment(msg.payload);
          setLastSeen(Date.now());
        }
      };
    };
    connect();
    return () => {
      closed = true;
      if (retry) window.clearTimeout(retry);
      socket?.close();
    };
  }, []);

  const applyAssessment = (row: Assessment | null | undefined) => {
    if (!row || !row.sensors) return;
    setAssessment(row);
    setLastSeen(Date.now());
  };

  const setExperience = (value: string) => {
    setExperienceState(value);
    api.setExperience(value).catch(() => undefined);
  };

  const value = useMemo(
    () => ({
      assessment,
      applyAssessment,
      connected,
      experience,
      setExperience,
      advanced: experience === "EXPERIENCED",
      collapsed,
      setCollapsed,
      search,
      setSearch,
      panel,
      setPanel,
      lastSeen,
      copilotOpen,
      setCopilotOpen,
    }),
    [assessment, connected, experience, collapsed, search, panel, lastSeen, copilotOpen],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useHydrated() {
  return useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );
}

export function useRuntime() {
  const value = useContext(Ctx);
  if (!value) throw new Error("useRuntime");
  return value;
}
