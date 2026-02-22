"use client";

import { useState, useEffect, useCallback } from "react";
import GithubRepoInput from "@/components/GithubRepoInput";

type Tab = "overview" | "jobs" | "new";

interface Job {
  job_id: string;
  repo_url?: string;
  branch?: string;
  status?: string;
  phase?: string;
  created_at?: string;
  allowed_geos?: string[];
  celery_state?: string;
  execution_celery_state?: string;
  estimated_job_spec?: Record<string, unknown>;
  [key: string]: unknown;
}

interface JobFiles {
  job_id: string;
  stage: string;
  file_count: number;
  text_file_count: number;
  binary_file_count: number;
  tree: Record<string, unknown>;
  key_files: string[];
  [key: string]: unknown;
}

interface AuditDecision {
  id: number;
  job_external_id: string;
  geo: string;
  provider: string;
  region: string;
  sku: string;
  score?: number | string | null;
  avg_delta?: number | string | null;
  reason_json?: Record<string, unknown>;
  created_at: string;
}

interface AuditMigrationEvent {
  id: number;
  job_external_id: string;
  status: string;
  message?: string | null;
  trigger_epoch?: number | null;
  from_region?: string | null;
  to_region?: string | null;
  reason_json?: Record<string, unknown>;
  created_at: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isPrimitive(value: unknown): value is string | number | boolean | null {
  return value === null || ["string", "number", "boolean"].includes(typeof value);
}

function toDisplayLabel(value: string): string {
  const normalized = value
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim();
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function formatPrimitive(value: string | number | boolean | null): string {
  if (value === null) return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : String(value);
  return value.length > 0 ? value : "Not set";
}

function toNumber(value: number | string | null | undefined): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function scoreToColor(score: number | null): string {
  if (score === null) return "rgba(148, 163, 184, 0.4)";
  const clamped = Math.max(0, Math.min(1, score));
  const hue = 230 - clamped * 180;
  return `hsla(${hue}, 85%, 52%, 0.65)`;
}

function ParallelAuditGraph({ decisions }: { decisions: AuditDecision[] }) {
  if (decisions.length === 0) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        No scheduling decisions yet.
      </p>
    );
  }

  const geos = Array.from(new Set(decisions.map((d) => d.geo).filter(Boolean))).sort();
  const providers = Array.from(new Set(decisions.map((d) => d.provider).filter(Boolean))).sort();
  const regions = Array.from(new Set(decisions.map((d) => d.region).filter(Boolean))).sort();
  const skus = Array.from(new Set(decisions.map((d) => d.sku).filter(Boolean))).sort();

  const avgDeltas = decisions
    .map((d) => toNumber(d.avg_delta))
    .filter((v): v is number => v !== null);
  const scores = decisions
    .map((d) => toNumber(d.score))
    .filter((v): v is number => v !== null);

  const minDelta = avgDeltas.length ? Math.min(...avgDeltas) : 0;
  const maxDelta = avgDeltas.length ? Math.max(...avgDeltas) : 1;
  const minScore = scores.length ? Math.min(...scores) : 0;
  const maxScore = scores.length ? Math.max(...scores) : 1;

  const width = 920;
  const height = 320;
  const top = 22;
  const bottom = 290;
  const left = 28;
  const right = 30;

  const axes = ["geo", "provider", "region", "sku", "avg_delta", "score"] as const;
  const xFor = (index: number) =>
    left + (index * (width - left - right)) / (axes.length - 1);

  const normalize = (value: number, min: number, max: number) => {
    if (max - min < 1e-9) return 0.5;
    return (value - min) / (max - min);
  };

  const yFromNormalized = (n: number) => bottom - n * (bottom - top);

  const categoryToY = (value: string, list: string[]) => {
    if (!list.length) return yFromNormalized(0.5);
    const idx = Math.max(0, list.indexOf(value));
    const n = list.length === 1 ? 0.5 : idx / (list.length - 1);
    return yFromNormalized(n);
  };

  const numberToY = (value: number | null, min: number, max: number) => {
    if (value === null) return yFromNormalized(0.5);
    return yFromNormalized(normalize(value, min, max));
  };

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-white/70 dark:bg-neutral-900/60">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-[920px] min-w-full h-[320px]">
          <defs>
            <linearGradient id="audit-score-gradient" x1="0" x2="0" y1="1" y2="0">
              <stop offset="0%" stopColor="#1d4ed8" />
              <stop offset="50%" stopColor="#db2777" />
              <stop offset="100%" stopColor="#facc15" />
            </linearGradient>
          </defs>

          {axes.map((axis, i) => {
            const x = xFor(i);
            const label = axis === "avg_delta" ? "avg delta" : axis;
            return (
              <g key={axis}>
                <line x1={x} y1={top} x2={x} y2={bottom} stroke="rgba(148,163,184,0.5)" strokeWidth="1" />
                <text
                  x={x}
                  y={14}
                  textAnchor="middle"
                  style={{ fontSize: "11px", fill: "rgb(82,82,91)", fontWeight: 600 }}
                >
                  {label}
                </text>
              </g>
            );
          })}

          {decisions.map((decision) => {
            const score = toNumber(decision.score);
            const avgDelta = toNumber(decision.avg_delta);
            const points = [
              `${xFor(0)},${categoryToY(decision.geo, geos)}`,
              `${xFor(1)},${categoryToY(decision.provider, providers)}`,
              `${xFor(2)},${categoryToY(decision.region, regions)}`,
              `${xFor(3)},${categoryToY(decision.sku, skus)}`,
              `${xFor(4)},${numberToY(avgDelta, minDelta, maxDelta)}`,
              `${xFor(5)},${numberToY(score, minScore, maxScore)}`,
            ].join(" ");

            return (
              <polyline
                key={decision.id}
                fill="none"
                points={points}
                stroke={scoreToColor(score)}
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            );
          })}

          <g>
            <rect x={width - 16} y={top} width="6" height={bottom - top} fill="url(#audit-score-gradient)" rx="2" />
            <text x={width - 20} y={top + 4} textAnchor="end" style={{ fontSize: "10px", fill: "rgb(82,82,91)" }}>
              high
            </text>
            <text x={width - 20} y={bottom} textAnchor="end" style={{ fontSize: "10px", fill: "rgb(82,82,91)" }}>
              low
            </text>
          </g>
        </svg>
      </div>

      <p className="text-xs text-neutral-500 dark:text-neutral-400">
        Parallel coordinates of scheduling decisions. Color intensity reflects score.
      </p>
    </div>
  );
}

function MigrationProgress({ events }: { events: AuditMigrationEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        No migration events yet.
      </p>
    );
  }

  const ordered = [...events].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  const completeCount = ordered.filter((event) =>
    ["completed", "success", "done", "applied"].includes((event.status ?? "").toLowerCase())
  ).length;
  const progress = Math.round((completeCount / ordered.length) * 100);

  return (
    <div className="space-y-4">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Migration Progress</p>
          <p className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">{progress}%</p>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
          <div
            className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-emerald-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="space-y-2">
        {ordered.map((event, index) => {
          const status = (event.status ?? "unknown").toLowerCase();
          const isComplete = ["completed", "success", "done", "applied"].includes(status);
          const isFailed = ["failed", "error"].includes(status);
          const tone = isFailed
            ? "bg-red-500"
            : isComplete
              ? "bg-emerald-500"
              : "bg-amber-500";

          return (
            <div
              key={event.id}
              className="grid grid-cols-[20px_1fr] gap-3 rounded-lg border border-neutral-200/60 bg-neutral-50/60 p-3 dark:border-neutral-800 dark:bg-neutral-900/50"
            >
              <div className="relative flex justify-center">
                <span className={`mt-1 h-2.5 w-2.5 rounded-full ${tone}`} />
                {index < ordered.length - 1 && (
                  <span className="absolute top-5 h-8 w-px bg-neutral-300 dark:bg-neutral-700" />
                )}
              </div>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-neutral-200 px-2 py-0.5 font-semibold uppercase tracking-wider text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
                    {status}
                  </span>
                  <span className="text-neutral-500 dark:text-neutral-400">
                    {new Date(event.created_at).toLocaleString()}
                  </span>
                  {typeof event.trigger_epoch === "number" && (
                    <span className="text-neutral-500 dark:text-neutral-400">epoch {event.trigger_epoch}</span>
                  )}
                </div>
                <p className="text-sm text-neutral-700 dark:text-neutral-300">
                  {event.message ?? "No migration message."}
                </p>
                {(event.from_region || event.to_region) && (
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    {event.from_region ?? "unknown"} {"->"} {event.to_region ?? "unknown"}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Status Badge ───────────────────────────────────────────────
function StatusBadge({ status }: { status?: string }) {
  const s = (status ?? "unknown").toLowerCase();
  const styles: Record<string, string> = {
    queued:
      "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/20",
    preparing:
      "bg-blue-500/10 text-blue-600 dark:text-blue-400 ring-blue-500/20",
    ready:
      "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/20",
    executing:
      "bg-violet-500/10 text-violet-600 dark:text-violet-400 ring-violet-500/20",
    done: "bg-green-500/10 text-green-600 dark:text-green-400 ring-green-500/20",
    completed:
      "bg-green-500/10 text-green-600 dark:text-green-400 ring-green-500/20",
    failed:
      "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/20",
    execution_queued:
      "bg-violet-500/10 text-violet-600 dark:text-violet-400 ring-violet-500/20",
  };
  const cls =
    styles[s] ??
    "bg-neutral-500/10 text-neutral-500 dark:text-neutral-400 ring-neutral-500/20";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${cls}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          ["preparing", "executing", "execution_queued"].includes(s)
            ? "animate-pulse bg-current"
            : "bg-current"
        }`}
      />
      {s.replace(/_/g, " ")}
    </span>
  );
}

// ─── Sidebar Icon helpers ───────────────────────────────────────
function IconOverview() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25a2.25 2.25 0 0 1-2.25-2.25v-2.25Z" />
    </svg>
  );
}
function IconJobs() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 0 1 0 3.75H5.625a1.875 1.875 0 0 1 0-3.75Z" />
    </svg>
  );
}
function IconNew() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

// ─── Stat Card ──────────────────────────────────────────────────
function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-neutral-200/60 dark:border-neutral-800 bg-white/60 dark:bg-neutral-900/60 backdrop-blur-sm p-5 transition-all hover:shadow-lg hover:shadow-blue-500/5 hover:border-blue-500/30">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/[0.02] to-transparent dark:from-blue-500/[0.04]" />
      <div className="relative">
        <p className="text-xs font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
          {label}
        </p>
        <p className={`mt-2 text-3xl font-bold tracking-tight ${accent ?? "text-neutral-900 dark:text-white"}`}>
          {value}
        </p>
        {sub && (
          <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">{sub}</p>
        )}
      </div>
    </div>
  );
}

function StructuredDataCard({ label, value }: { label: string; value: unknown }) {
  if (isRecord(value)) {
    const entries = Object.entries(value);
    return (
      <div className="rounded-lg border border-neutral-200/70 bg-white/70 p-3 dark:border-neutral-800 dark:bg-neutral-950/40">
        <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
          {label}
        </p>
        {entries.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">No fields</p>
        ) : (
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {entries.map(([nestedKey, nestedValue]) => (
              <StructuredDataCard
                key={`${label}-${nestedKey}`}
                label={toDisplayLabel(nestedKey)}
                value={nestedValue}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  if (Array.isArray(value)) {
    const primitiveItems = value.filter(isPrimitive);
    const hasOnlyPrimitiveItems = primitiveItems.length === value.length;

    return (
      <div className="rounded-lg border border-neutral-200/70 bg-white/70 p-3 dark:border-neutral-800 dark:bg-neutral-950/40">
        <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
          {label}
        </p>
        {value.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">None</p>
        ) : hasOnlyPrimitiveItems ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {primitiveItems.map((item, index) => (
              <span
                key={`${label}-${index}`}
                className="rounded-md bg-neutral-200/70 px-2 py-0.5 text-xs font-medium text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
              >
                {formatPrimitive(item)}
              </span>
            ))}
          </div>
        ) : (
          <div className="mt-2 space-y-2">
            {value.map((item, index) => (
              <StructuredDataCard
                key={`${label}-${index}`}
                label={`Item ${index + 1}`}
                value={item}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200/70 bg-white/70 p-3 dark:border-neutral-800 dark:bg-neutral-950/40">
      <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
        {label}
      </p>
      <p className="mt-1 text-sm font-medium text-neutral-800 dark:text-neutral-200 break-words">
        {formatPrimitive(isPrimitive(value) ? value : null)}
      </p>
    </div>
  );
}

function StructuredDataView({
  data,
  emptyText,
}: {
  data?: Record<string, unknown>;
  emptyText: string;
}) {
  if (!data || Object.keys(data).length === 0) {
    return <p className="text-sm text-neutral-500 dark:text-neutral-400">{emptyText}</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {Object.entries(data).map(([key, value]) => (
        <StructuredDataCard key={key} label={toDisplayLabel(key)} value={value} />
      ))}
    </div>
  );
}

// ─── File Tree ──────────────────────────────────────────────────
function FileTree({ tree, depth = 0 }: { tree: Record<string, unknown>; depth?: number }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <ul className={depth === 0 ? "space-y-0.5" : "ml-4 space-y-0.5"}>
      {Object.entries(tree).map(([key, val]) => {
        const isDir = val !== null && typeof val === "object" && !Array.isArray(val);
        const isOpen = expanded.has(key);
        return (
          <li key={key}>
            {isDir ? (
              <>
                <button
                  onClick={() => toggle(key)}
                  className="flex items-center gap-1.5 w-full text-left py-0.5 px-1.5 rounded text-sm hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                >
                  <svg
                    className={`w-3.5 h-3.5 text-neutral-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                  <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z" />
                  </svg>
                  <span className="text-neutral-700 dark:text-neutral-300 font-medium">{key}</span>
                </button>
                {isOpen && <FileTree tree={val as Record<string, unknown>} depth={depth + 1} />}
              </>
            ) : (
              <div className="flex items-center gap-1.5 py-0.5 px-1.5 ml-5 text-sm text-neutral-600 dark:text-neutral-400">
                <svg className="w-4 h-4 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                </svg>
                {key}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// ─── Job Detail Panel ───────────────────────────────────────────
function JobDetailPanel({
  job,
  onClose,
  onExecute,
}: {
  job: Job;
  onClose: () => void;
  onExecute: (jobId: string) => void;
}) {
  const [detail, setDetail] = useState<Job | null>(null);
  const [files, setFiles] = useState<JobFiles | null>(null);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [activeFileTab, setActiveFileTab] = useState<"prepared" | "source">("prepared");
  const [auditDecisions, setAuditDecisions] = useState<AuditDecision[]>([]);
  const [auditMigrations, setAuditMigrations] = useState<AuditMigrationEvent[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(true);
  const [auditError, setAuditError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${job.job_id}`);
        if (res.ok && !cancelled) {
          const data = await res.json();
          setDetail(data);
        }
      } catch {
        /* ignore */
      }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [job.job_id]);

  useEffect(() => {
    let cancelled = false;
    const pollAudit = async () => {
      try {
        if (!cancelled) setLoadingAudit(true);
        const res = await fetch(`/api/audit/${job.job_id}`);
        const data = await res.json().catch(() => null);

        if (!cancelled) {
          if (res.ok && data) {
            setAuditDecisions(
              Array.isArray(data.schedulingDecisions)
                ? (data.schedulingDecisions as AuditDecision[])
                : []
            );
            setAuditMigrations(
              Array.isArray(data.migrationEvents)
                ? (data.migrationEvents as AuditMigrationEvent[])
                : []
            );
            setAuditError(null);
          } else {
            setAuditError("Could not load audit trail.");
          }
        }
      } catch {
        if (!cancelled) setAuditError("Could not load audit trail.");
      } finally {
        if (!cancelled) setLoadingAudit(false);
      }
    };

    pollAudit();
    const interval = setInterval(pollAudit, 10000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [job.job_id]);

  const loadFiles = async (stage: "prepared" | "source") => {
    setLoadingFiles(true);
    setActiveFileTab(stage);
    try {
      const res = await fetch(`/api/jobs/${job.job_id}/files?stage=${stage}`);
      if (res.ok) setFiles(await res.json());
    } catch {
      /* ignore */
    } finally {
      setLoadingFiles(false);
    }
  };

  const d = detail ?? job;
  const spec = d.estimated_job_spec as Record<string, unknown> | undefined;
  const canExecute = d.phase === "ready" || d.status === "ready" || d.phase === "prepared";
  const latestDecision = auditDecisions[0] ?? null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="relative h-full w-full max-w-2xl overflow-y-auto bg-white dark:bg-neutral-950 border-l border-neutral-200 dark:border-neutral-800 shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 bg-white/80 dark:bg-neutral-950/80 backdrop-blur-sm px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-neutral-900 dark:text-white truncate">
                Job Detail
              </h2>
              <StatusBadge status={d.phase ?? d.status} />
            </div>
            <p className="text-xs font-mono text-neutral-500 mt-0.5 truncate">{d.job_id}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Status + Actions */}
          <div className="flex flex-wrap gap-3">
            {canExecute && (
              <button
                onClick={() => onExecute(d.job_id)}
                className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700 hover:shadow-emerald-500/20 hover:shadow-lg"
              >
                Execute Job
              </button>
            )}
            <button
              onClick={() => loadFiles("prepared")}
              className="rounded-xl border border-neutral-200 dark:border-neutral-700 px-5 py-2.5 text-sm font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
            >
              View Prepared Files
            </button>
            <button
              onClick={() => loadFiles("source")}
              className="rounded-xl border border-neutral-200 dark:border-neutral-700 px-5 py-2.5 text-sm font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
            >
              View Source Files
            </button>
          </div>

          {/* Info Grid */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Repository", value: d.repo_url },
              { label: "Branch", value: d.branch ?? "main" },
              { label: "Phase", value: d.phase ?? d.status },
              { label: "Celery State", value: d.celery_state ?? "—" },
              { label: "Exec State", value: d.execution_celery_state ?? "—" },
              { label: "Allowed Geos", value: Array.isArray(d.allowed_geos) ? d.allowed_geos.join(", ") : "—" },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/50 p-3"
              >
                <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-400">{label}</p>
                <p className="mt-1 text-sm font-medium text-neutral-800 dark:text-neutral-200 truncate">
                  {String(value ?? "—")}
                </p>
              </div>
            ))}
          </div>

          {/* Estimated Job Spec */}
          {spec && Object.keys(spec).length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300">
                Estimated Job Spec
              </h3>
              <div className="rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/50 p-4">
                <StructuredDataView data={spec} emptyText="No estimated spec available." />
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300">
                Audit Trail
              </h3>
              <div className="flex gap-2 text-xs text-neutral-500">
                <span>{auditDecisions.length} decisions</span>
                <span>&middot;</span>
                <span>{auditMigrations.length} migrations</span>
              </div>
            </div>

            {loadingAudit ? (
              <div className="flex items-center justify-center py-8">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
              </div>
            ) : auditError ? (
              <p className="text-sm text-red-500">{auditError}</p>
            ) : (
              <>
                <div className="rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/50 p-4">
                  <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                    Decision Graph
                  </h4>
                  <ParallelAuditGraph decisions={auditDecisions} />
                </div>

                {latestDecision && (
                  <div className="rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/50 p-4">
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                      Latest Decision Reason
                    </h4>
                    <StructuredDataView
                      data={latestDecision.reason_json}
                      emptyText="No decision reason details available."
                    />
                  </div>
                )}

                <div className="rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/50 p-4">
                  <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                    Migration Timeline
                  </h4>
                  <MigrationProgress events={auditMigrations} />
                </div>
              </>
            )}
          </div>

          {/* File Tree */}
          {files && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300">
                  Files ({activeFileTab})
                </h3>
                <div className="flex gap-2 text-xs text-neutral-500">
                  <span>{files.file_count} total</span>
                  <span>&middot;</span>
                  <span>{files.text_file_count} text</span>
                  <span>&middot;</span>
                  <span>{files.binary_file_count} binary</span>
                </div>
              </div>
              {loadingFiles ? (
                <div className="flex items-center justify-center py-8">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                </div>
              ) : files.tree ? (
                <div className="rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/50 p-4 max-h-96 overflow-y-auto">
                  <FileTree tree={files.tree as Record<string, unknown>} />
                </div>
              ) : (
                <p className="text-sm text-neutral-500">No file tree available.</p>
              )}

              {files.key_files && files.key_files.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-400">Key Files</h4>
                  <div className="flex flex-wrap gap-2">
                    {files.key_files.map((f) => (
                      <span key={f} className="rounded-lg bg-blue-500/10 px-2.5 py-1 text-xs font-mono text-blue-600 dark:text-blue-400 ring-1 ring-inset ring-blue-500/20">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// MAIN DASHBOARD CLIENT
// ═══════════════════════════════════════════════════════════════════
export default function DashboardClient({
  userEmail,
}: {
  userEmail: string;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobCount, setJobCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch("/api/jobs");
      if (res.ok) {
        const data = await res.json();
        const list: Job[] = Array.isArray(data.jobs) ? data.jobs : [];
        setJobs(list);
        setJobCount(typeof data.count === "number" ? data.count : list.length);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const activeJobs = jobs.filter((j) =>
    ["preparing", "executing", "queued", "execution_queued"].includes(
      (j.phase ?? j.status ?? "").toLowerCase()
    )
  );
  const completedJobs = jobs.filter((j) =>
    ["done", "completed", "ready"].includes((j.phase ?? j.status ?? "").toLowerCase())
  );

  async function handleExecute(jobId: string) {
    try {
      await fetch(`/api/jobs/${jobId}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      fetchJobs();
    } catch {
      /* ignore */
    }
  }

  async function handleNewJob(url: string) {
    try {
      await fetch("/api/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url }),
      });
      setTab("jobs");
      fetchJobs();
    } catch {
      /* ignore */
    }
  }

  const navItems: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: "Overview", icon: <IconOverview /> },
    { id: "jobs", label: "Jobs", icon: <IconJobs /> },
    { id: "new", label: "New Training", icon: <IconNew /> },
  ];

  return (
    <div className="flex min-h-screen">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* ─── Sidebar ─── */}
      <aside
        className={`fixed md:sticky top-0 left-0 z-40 h-screen w-64 shrink-0 border-r border-neutral-200/60 dark:border-neutral-800 bg-white/80 dark:bg-neutral-950/80 backdrop-blur-xl flex flex-col transition-transform duration-300 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex items-center gap-3 px-5 py-5 border-b border-neutral-200/60 dark:border-neutral-800">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 text-white font-bold text-sm shadow-lg shadow-blue-500/20">
            S
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-neutral-900 dark:text-white">Sustain</p>
            <p className="text-[11px] text-neutral-500 truncate">{userEmail}</p>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setTab(item.id);
                setSidebarOpen(false);
              }}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                tab === item.id
                  ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 shadow-sm"
                  : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800/60 hover:text-neutral-900 dark:hover:text-white"
              }`}
            >
              {item.icon}
              {item.label}
              {item.id === "jobs" && jobCount > 0 && (
                <span className="ml-auto rounded-full bg-neutral-200 dark:bg-neutral-800 px-2 py-0.5 text-[10px] font-bold text-neutral-600 dark:text-neutral-400">
                  {jobCount}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="border-t border-neutral-200/60 dark:border-neutral-800 p-3">
          <button
            onClick={() => { window.location.href = "/"; }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-600 dark:text-neutral-400 hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-400 transition-all"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
            </svg>
            Sign Out
          </button>
        </div>
      </aside>

      {/* ─── Main content ─── */}
      <div className="flex-1 min-w-0">
        {/* Top bar (mobile) */}
        <div className="sticky top-0 z-30 flex items-center justify-between border-b border-neutral-200/60 dark:border-neutral-800 bg-white/80 dark:bg-neutral-950/80 backdrop-blur-xl px-4 py-3 md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <span className="text-sm font-bold text-neutral-900 dark:text-white">
            {navItems.find((n) => n.id === tab)?.label}
          </span>
          <div className="w-9" />
        </div>

        <div className="p-6 md:p-8 lg:p-10">
          {/* ─── Overview Tab ─── */}
          {tab === "overview" && (
            <div className="space-y-8">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white">
                  Overview
                </h1>
                <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
                  Your green compute dashboard
                </p>
              </div>

              {/* Stat cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  label="Total Jobs"
                  value={loading ? "—" : jobCount}
                  sub="Across all regions"
                />
                <StatCard
                  label="Active"
                  value={loading ? "—" : activeJobs.length}
                  sub="Preparing or executing"
                  accent="text-blue-600 dark:text-blue-400"
                />
                <StatCard
                  label="Completed"
                  value={loading ? "—" : completedJobs.length}
                  sub="Ready or done"
                  accent="text-emerald-600 dark:text-emerald-400"
                />
                <StatCard
                  label="CO\u2082 Optimized"
                  value={loading ? "—" : `${Math.max(0, completedJobs.length * 12)}kg`}
                  sub="Estimated savings"
                  accent="text-green-600 dark:text-green-400"
                />
              </div>

              {/* Recent jobs */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">
                    Recent Jobs
                  </h2>
                  <button
                    onClick={() => setTab("jobs")}
                    className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    View all
                  </button>
                </div>

                {loading ? (
                  <div className="flex items-center justify-center py-16">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                  </div>
                ) : jobs.length === 0 ? (
                  <div className="rounded-2xl border-2 border-dashed border-neutral-200 dark:border-neutral-800 p-12 text-center">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10">
                      <IconNew />
                    </div>
                    <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      No jobs yet
                    </p>
                    <p className="mt-1 text-sm text-neutral-500">
                      Submit a repository to start green training
                    </p>
                    <button
                      onClick={() => setTab("new")}
                      className="mt-4 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
                    >
                      New Training
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {jobs.slice(0, 5).map((job) => (
                      <button
                        key={job.job_id}
                        onClick={() => setSelectedJob(job)}
                        className="flex w-full items-center justify-between rounded-xl border border-neutral-200/60 dark:border-neutral-800 bg-white/60 dark:bg-neutral-900/40 backdrop-blur-sm p-4 text-left transition-all hover:shadow-md hover:border-blue-500/30 group"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-neutral-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                            {job.repo_url ?? job.job_id}
                          </p>
                          <p className="text-xs text-neutral-500 font-mono mt-0.5 truncate">
                            {job.job_id}
                          </p>
                        </div>
                        <div className="ml-4 shrink-0">
                          <StatusBadge status={job.phase ?? job.status} />
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ─── Jobs Tab ─── */}
          {tab === "jobs" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white">
                    Jobs
                  </h1>
                  <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
                    {jobCount} total job{jobCount !== 1 ? "s" : ""}
                  </p>
                </div>
                <button
                  onClick={() => setTab("new")}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
                >
                  <IconNew />
                  New Job
                </button>
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                </div>
              ) : jobs.length === 0 ? (
                <div className="rounded-2xl border-2 border-dashed border-neutral-200 dark:border-neutral-800 p-16 text-center">
                  <p className="text-sm text-neutral-500">No jobs found. Create one to get started.</p>
                </div>
              ) : (
                <div className="overflow-hidden rounded-2xl border border-neutral-200/60 dark:border-neutral-800 bg-white/60 dark:bg-neutral-900/40 backdrop-blur-sm">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/80 dark:bg-neutral-900/80">
                        {["Repository", "Branch", "Status", "Geos", "Actions"].map(
                          (h) => (
                            <th
                              key={h}
                              className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-neutral-500"
                            >
                              {h}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-200/60 dark:divide-neutral-800">
                      {jobs.map((job) => {
                        const canExec = ["ready", "prepared"].includes(
                          (job.phase ?? "").toLowerCase()
                        );
                        return (
                          <tr
                            key={job.job_id}
                            className="transition-colors hover:bg-neutral-50/60 dark:hover:bg-neutral-800/40 cursor-pointer"
                            onClick={() => setSelectedJob(job)}
                          >
                            <td className="px-5 py-4">
                              <p className="text-sm font-medium text-neutral-900 dark:text-white truncate max-w-[250px]">
                                {job.repo_url ?? "—"}
                              </p>
                              <p className="text-[11px] font-mono text-neutral-400 mt-0.5 truncate max-w-[250px]">
                                {job.job_id}
                              </p>
                            </td>
                            <td className="px-5 py-4 text-sm text-neutral-600 dark:text-neutral-400">
                              {job.branch ?? "main"}
                            </td>
                            <td className="px-5 py-4">
                              <StatusBadge status={job.phase ?? job.status} />
                            </td>
                            <td className="px-5 py-4 text-sm text-neutral-600 dark:text-neutral-400">
                              {Array.isArray(job.allowed_geos)
                                ? job.allowed_geos.join(", ")
                                : "—"}
                            </td>
                            <td className="px-5 py-4">
                              {canExec && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleExecute(job.job_id);
                                  }}
                                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors"
                                >
                                  Execute
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ─── New Training Tab ─── */}
          {tab === "new" && (
            <div className="space-y-8 max-w-xl">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white">
                  New Training Job
                </h1>
                <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
                  Submit a GitHub repository for green compute optimization
                </p>
              </div>

              <div className="rounded-2xl border border-neutral-200/60 dark:border-neutral-800 bg-white/60 dark:bg-neutral-900/40 backdrop-blur-sm p-8 space-y-6">
                <div>
                  <label className="block text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
                    Repository URL
                  </label>
                  <GithubRepoInput onSubmit={handleNewJob} />
                </div>
                <p className="text-xs text-neutral-400 dark:text-neutral-500 leading-relaxed">
                  We&apos;ll analyze your repository, find the greenest compute window, and prepare it for energy-optimized training.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ─── Job Detail Slide-over ─── */}
      {selectedJob && (
        <JobDetailPanel
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onExecute={handleExecute}
        />
      )}
    </div>
  );
}
