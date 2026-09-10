"use client";

import { cn } from "@/lib/format";

export function Card({
  title,
  kicker,
  children,
  className,
  action,
}: {
  title?: string;
  kicker?: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <section className={cn("card p-4", className)}>
      {(kicker || title || action) && (
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            {kicker && <div className="kicker">{kicker}</div>}
            {title && <div className="text-sm font-semibold tracking-wide">{title}</div>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Badge({ level, children }: { level?: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider", `risk-${(level || "UNKNOWN").toUpperCase().replace(" ", "")}`)}>
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  type = "button",
  disabled,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
  disabled?: boolean;
}) {
  const styles = {
    primary: "bg-[#d5dee6] text-[#07090c] hover:bg-white",
    ghost: "border border-[#24303a] bg-transparent text-[#d5dee6] hover:bg-[#1a242c]",
    danger: "border border-[#e24a4a] text-[#ffb0b0] bg-transparent",
  };
  return (
    <button type={type} disabled={disabled} onClick={onClick} className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition", styles[variant], disabled && "opacity-50")}>
      {children}
    </button>
  );
}

export function Empty({ title, body }: { title: string; children?: React.ReactNode; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[#24303a] bg-[#0c1116] p-6 text-center">
      <div className="text-sm font-semibold">{title}</div>
      <p className="mt-1 text-sm text-[#7d8b96]">{body}</p>
    </div>
  );
}

export function Loading({ title = "Connecting to AERA", body = "Waiting for live Motor 01 telemetry." }: { title?: string; body?: string }) {
  return <Empty title={title} body={body} />;
}

export function Overlay({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
      <div className="max-h-[82vh] w-full max-w-2xl overflow-auto rounded-xl border border-[#24303a] bg-[#10161c] p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm font-semibold">{title}</div>
          <button onClick={onClose} className="text-xs uppercase tracking-widest text-[#5b7388]">
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Chip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-[#d9e1e8] bg-[#f8fafb] px-2 py-0.5 text-[11px] text-[#1d5f8a]">{children}</span>;
}

export function Bar({ value, tone = "green" }: { value: number; tone?: "green" | "amber" | "red" | "blue" }) {
  const color = { green: "#2f9e44", amber: "#c98412", red: "#c62828", blue: "#1d5f8a" }[tone];
  return (
    <div className="bar">
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
    </div>
  );
}
