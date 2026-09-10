export type RiskLevel = "NORMAL" | "MONITOR" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN";

export interface Deviation {
  name: string;
  title: string;
  unit: string;
  value: number;
  expected: number;
  delta: number;
  z: number;
  rate: number;
  percent_change: number;
  severity: string;
  unusual: boolean;
  note: string;
  meaning?: string;
}

export interface Assessment {
  timestamp?: string;
  connected: boolean;
  source?: string;
  error?: string;
  motor?: {
    code?: string;
    tag?: string;
    name?: string;
    status?: string;
    operating_mode?: string;
    health_status?: string;
    direction?: string;
    drive_status?: string;
    scenario?: string;
    fault_state?: boolean | string;
  };
  sensors?: Record<string, number>;
  health?: number;
  risk?: {
    score: number;
    level: RiskLevel;
    reason: string;
    evidence: string[];
    trend: string;
    historical_frequency: number;
    potential_consequence: string;
    recommended_response: string;
    factors: Record<string, number>;
    failure_association?: number;
  };
  situation?: {
    id?: string;
    title: string;
    family?: string;
    what?: string;
    why?: string;
    possible_cause?: string;
    consequence?: string;
    signals?: string[];
    sop?: string;
    checks?: string[];
    avoid?: string[];
  };
  deviations?: Deviation[];
  why_flagged?: { flagged?: boolean; points: string[]; attention?: string; score?: number; factors?: Record<string, number> };
  why_not_flagged?: { points: string[] };
  similar?: {
    count: number;
    failure_count?: number;
    intervention_count?: number;
    bearing_count?: number;
    summary?: string;
    matches?: Array<{
      event_number: number;
      date?: string;
      symptoms?: string;
      root_cause?: string;
      operator_action?: string;
      solution?: string;
      outcome?: string;
      similarity?: number;
      failure?: boolean;
      intervention?: boolean;
    }>;
  };
  guidance?: {
    checks: Array<{ step: number; action: string; reason: string }>;
    avoid: string[];
    sop?: { code: string; title: string; steps: string[]; safety: string[] } | null;
    expert?: Array<Record<string, unknown>>;
    previous_solutions?: Array<Record<string, string>>;
    escalate?: boolean;
    escalate_reason?: string;
  };
  narrative?: string;
  alarms?: Array<Record<string, unknown>>;
  timeline?: Array<{ time: string; label: string; detail: string }>;
  parameters?: Record<string, Record<string, unknown>>;
  series?: Record<string, Array<{ t: string; v: number }>>;
  experience_level?: string;
  attention?: string;
  copilot_view?: CopilotView;
  recommendation?: Recommendation;
  events?: MachineEvent[];
}

export interface MachineEvent {
  id?: number;
  timestamp?: string;
  date?: string;
  clock?: string;
  event_type: string;
  message?: string;
  alarm_status?: string;
  event_kind?: string;
  parameter?: string;
  previous?: number | string | null;
  new?: number | string | null;
  unit?: string;
  severity?: string;
  source?: string;
  context?: string;
  condition?: string;
  equipment?: string;
  aera_assessment?: string;
  recommendation?: string;
  operator_response?: string;
  outcome?: string;
}

export interface Recommendation {
  key?: string;
  status?: string;
  primary?: string;
  alternative?: string[];
  detected_at?: string;
  analyzed_at?: string;
  recommended_at?: string;
  rejected_reason?: string;
  applied?: boolean;
  history_minutes?: number;
  actionable?: boolean;
}

export interface CopilotView {
  status?: string;
  what?: string;
  analysis?: string;
  history?: string;
  risk?: string;
  cause?: string;
  cause_certainty?: string;
  action?: string;
  alert?: boolean;
  alternative?: string[];
  successful_action?: string;
  similar_count?: number;
  intervention_count?: number;
  failure_count?: number;
  history_minutes?: number;
  timings?: {
    detected?: string;
    analyzed?: string;
    recommendation?: string;
  };
  recommendation?: Recommendation;
}
