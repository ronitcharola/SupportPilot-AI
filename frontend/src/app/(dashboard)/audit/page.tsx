"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { api, AuditLogEntry, AuditLogListResponse } from "@/lib/api";
import { useToast } from "@/components/toast";
import {
  FileText,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Shield,
  Lock,
  CheckCircle2,
  LogIn,
  LogOut,
  ShieldAlert,
  UserCog,
  Cpu,
  Eye,
  Clock,
  Filter,
} from "lucide-react";
import { cn } from "@/lib/utils";

const CATEGORY_TABS = [
  { label: "All Events", value: "" },
  { label: "Auth", value: "auth" },
  { label: "Proposals", value: "proposal" },
  { label: "Tickets", value: "ticket" },
  { label: "Workspace", value: "workspace" },
  { label: "AI", value: "ai" },
];

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  auth: LogIn,
  proposal: ShieldAlert,
  ticket: FileText,
  workspace: UserCog,
  ai: Cpu,
};

const CATEGORY_COLORS: Record<string, string> = {
  auth: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  proposal: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  ticket: "text-cyan-400 bg-cyan-500/10 border-cyan-500/30",
  workspace: "text-violet-400 bg-violet-500/10 border-violet-500/30",
  ai: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
};

export default function AuditPage() {
  const { activeWorkspace } = useAuth();
  const toast = useToast();
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const res: AuditLogListResponse = await api.audit.list({
        event_category: categoryFilter || undefined,
        event_type: eventTypeFilter || undefined,
        page,
        page_size: 25,
      });
      setEntries(res.items);
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch (err: any) {
      toast.error("Failed to load audit logs", err.message);
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, eventTypeFilter, page, activeWorkspace?.workspace_id]);

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <FileText className="w-6 h-6 text-indigo-400" />
          Immutable Audit Trail
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Append-only, workspace-scoped compliance log. Rows are written by server services only — no
          create, update, or delete API verbs exist.
        </p>
      </div>

      {/* Guarantees Banner */}
      <div className="glass-card rounded-xl p-4 border border-indigo-500/20 bg-indigo-950/10">
        <div className="flex items-start gap-3">
          <Lock className="w-4 h-4 text-indigo-400 mt-0.5 flex-shrink-0" />
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-400">
            <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-indigo-400/60" /> Strict append-only (no update/delete)</span>
            <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-indigo-400/60" /> Zero secret leakage</span>
            <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-indigo-400/60" /> Admin-only access</span>
            <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-indigo-400/60" /> Workspace-scoped isolation</span>
          </div>
        </div>
      </div>

      {/* Category Filter Tabs */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {CATEGORY_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => { setCategoryFilter(tab.value); setPage(1); setExpandedId(null); }}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
              categoryFilter === tab.value
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                : "bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-800"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Event Type Filter */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Filter className="w-3.5 h-3.5" />
          <span>Event type:</span>
        </div>
        <input
          type="text"
          value={eventTypeFilter}
          onChange={(e) => { setEventTypeFilter(e.target.value); setPage(1); }}
          placeholder="e.g. proposal_approved, login"
          className="px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-white text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 w-64"
        />
        {eventTypeFilter && (
          <button
            onClick={() => setEventTypeFilter("")}
            className="text-[10px] text-slate-400 hover:text-white"
          >
            Clear
          </button>
        )}
        <span className="ml-auto text-[10px] text-slate-500 tabular-nums">{total} events total</span>
      </div>

      {/* Audit Log Table */}
      <div className="glass-card rounded-xl border border-slate-800 overflow-hidden">
        {loading ? (
          <div className="p-12 flex items-center justify-center gap-2 text-slate-400 text-xs">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
            Loading audit events...
          </div>
        ) : entries.length === 0 ? (
          <div className="p-12 text-center">
            <FileText className="w-8 h-8 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-400">No audit events found</p>
            <p className="text-[10px] text-slate-500 mt-1">
              Events are written automatically when auth, approval, or workspace actions occur.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-medium bg-slate-900/40">
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Target</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {entries.map((entry) => {
                  const CategoryIcon = CATEGORY_ICONS[entry.event_category] || FileText;
                  const colorClass = CATEGORY_COLORS[entry.event_category] || CATEGORY_COLORS.auth;
                  const isExpanded = expandedId === entry.id;

                  return (
                    <React.Fragment key={entry.id}>
                      <tr
                        className="hover:bg-slate-900/40 transition-colors cursor-pointer"
                        onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                      >
                        <td className="py-3 px-4 text-slate-300 font-mono text-[10px] whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3 h-3 text-slate-500" />
                            {formatDate(entry.created_at)}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className={cn(
                            "inline-flex items-center gap-1 text-[9px] font-semibold uppercase px-2 py-0.5 rounded-full border",
                            colorClass
                          )}>
                            <CategoryIcon className="w-3 h-3" />
                            {entry.event_category}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-white font-medium font-mono text-[11px]">
                          {entry.event_type}
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-slate-300">{entry.actor_email || "—"}</span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex flex-col">
                            {entry.target_ticket_id && (
                              <span className="text-[10px] text-cyan-400 font-mono">
                                ticket: {entry.target_ticket_id.slice(0, 8)}…
                              </span>
                            )}
                            {entry.target_proposal_id && (
                              <span className="text-[10px] text-amber-400 font-mono">
                                proposal: {entry.target_proposal_id.slice(0, 8)}…
                              </span>
                            )}
                            {!entry.target_ticket_id && !entry.target_proposal_id && (
                              <span className="text-slate-500">—</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 ml-auto">
                            <Eye className="w-3 h-3" />
                            {isExpanded ? "Hide" : "Show"}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded detail row */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={6} className="px-4 pb-4 bg-slate-900/30">
                            <div className="rounded-lg border border-slate-700/50 p-3 space-y-2">
                              {entry.details && Object.keys(entry.details).length > 0 ? (
                                <div>
                                  <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
                                    Event Payload
                                  </span>
                                  <pre className="text-[10px] text-slate-300 font-mono bg-slate-900/80 p-2 rounded overflow-x-auto">
                                    {JSON.stringify(entry.details, null, 2)}
                                  </pre>
                                </div>
                              ) : (
                                <p className="text-[10px] text-slate-500">No additional details</p>
                              )}
                              <div className="flex flex-wrap gap-x-6 gap-y-1 text-[10px] text-slate-500">
                                <span>Event ID: <span className="font-mono text-slate-400">{entry.id}</span></span>
                                {entry.ip_address && (
                                  <span>IP: <span className="font-mono text-slate-400">{entry.ip_address}</span></span>
                                )}
                                {entry.user_agent && (
                                  <span className="truncate max-w-xs" title={entry.user_agent}>
                                    UA: <span className="font-mono text-slate-400">{entry.user_agent.slice(0, 60)}…</span>
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> Previous
          </button>
          <span className="text-[10px] text-slate-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
          >
            Next <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
