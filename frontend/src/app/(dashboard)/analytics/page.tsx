"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import { api, AnalyticsOverview } from "@/lib/api";
import {
  BarChart3,
  Loader2,
  AlertTriangle,
  Inbox,
  Clock,
  Activity,
  CheckCircle2,
  ShieldAlert,
  TrendingUp,
  Sparkles,
  ArrowRight,
  FileText,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";

const STATUS_COLORS: Record<string, string> = {
  open: "#22c55e",
  in_progress: "#3b82f6",
  pending_approval: "#a855f7",
  waiting_for_customer: "#f59e0b",
  escalated: "#ef4444",
  resolved: "#10b981",
  closed: "#6b7280",
};

const PIE_COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#3b82f6", "#a855f7", "#10b981", "#e879f9"];

export default function AnalyticsPage() {
  const { activeWorkspace } = useAuth();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.analytics.overview();
        setOverview(data);
      } catch (err: any) {
        setError(err.message || "Failed to load analytics");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [activeWorkspace?.workspace_id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex items-center gap-3 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
          <span className="text-sm font-medium">Loading analytics...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto py-20 text-center">
        <div className="glass-card rounded-2xl p-8 border border-slate-800">
          <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-white mb-2">Analytics Error</h3>
          <p className="text-xs text-slate-400 mb-4">{error}</p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!overview) return null;

  // Compute derived metrics
  const resolutionRate = overview.total_tickets > 0
    ? Math.round(((overview.resolved_tickets + overview.closed_tickets) / overview.total_tickets) * 100)
    : 0;

  const escalationRate = overview.total_tickets > 0
    ? Math.round((overview.escalated_tickets / overview.total_tickets) * 100)
    : 0;

  const activeTickets = overview.open_tickets + overview.in_progress_tickets;

  const metricCards = [
    { label: "Total Tickets", value: overview.total_tickets, icon: Inbox, color: "text-white", bg: "bg-slate-800/60" },
    { label: "Active", value: activeTickets, icon: Activity, color: "text-blue-400", bg: "bg-blue-500/10" },
    { label: "Resolved", value: overview.resolved_tickets, icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "Escalated", value: overview.escalated_tickets, icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10" },
    { label: "Resolution Rate", value: `${resolutionRate}%`, icon: TrendingUp, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "Escalation Rate", value: `${escalationRate}%`, icon: ShieldAlert, color: "text-amber-400", bg: "bg-amber-500/10" },
    { label: "Pending Proposals", value: overview.pending_proposals, icon: Clock, color: "text-violet-400", bg: "bg-violet-500/10" },
    { label: "Audit Events (24h)", value: overview.recent_audit_events_24h, icon: FileText, color: "text-indigo-400", bg: "bg-indigo-500/10" },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <BarChart3 className="w-6 h-6 text-indigo-400" />
            Analytics & Performance Metrics
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time workspace-scoped metrics computed from server-side aggregate queries.
            No frontend estimation — all numbers are authoritative.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium transition-all flex items-center gap-1.5 border border-slate-700"
          >
            Dashboard
          </Link>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {metricCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="glass-card rounded-xl p-4 border border-slate-800 hover:border-indigo-500/30 transition-all duration-200"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
                  {card.label}
                </span>
                <div className={`w-6 h-6 rounded-lg ${card.bg} flex items-center justify-center`}>
                  <Icon className={`w-3 h-3 ${card.color}`} />
                </div>
              </div>
              <div className={`text-2xl font-bold ${card.color} tabular-nums`}>
                {card.value}
              </div>
            </div>
          );
        })}
      </div>

      {/* Charts Row 1: Status + Category */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution Bar Chart */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            Ticket Status Distribution
          </h3>
          {overview.status_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={overview.status_distribution} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="status"
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  tickFormatter={(v: string) => v.replace(/_/g, " ")}
                  axisLine={{ stroke: "#334155" }}
                />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={{ stroke: "#334155" }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "12px",
                    fontSize: "11px",
                    color: "#e2e8f0",
                  }}
                  labelFormatter={(v) => String(v).replace(/_/g, " ")}
                />
                <Bar dataKey="count" name="Tickets" radius={[6, 6, 0, 0]}>
                  {overview.status_distribution.map((entry, index) => (
                    <Cell key={index} fill={STATUS_COLORS[entry.status] || "#6366f1"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-72 flex items-center justify-center text-xs text-slate-500">No data</div>
          )}
        </div>

        {/* Category Pie Chart */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Category Breakdown
          </h3>
          {overview.category_distribution.length > 0 ? (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="60%" height={260}>
                <PieChart>
                  <Pie
                    data={overview.category_distribution}
                    dataKey="count"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    innerRadius={50}
                    paddingAngle={3}
                  >
                    {overview.category_distribution.map((_entry, index) => (
                      <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "12px",
                      fontSize: "11px",
                      color: "#e2e8f0",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {overview.category_distribution.map((entry, index) => (
                  <div key={entry.category} className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                      style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }}
                    />
                    <span className="text-[10px] text-slate-300 capitalize">
                      {entry.category.replace(/_/g, " ")}
                    </span>
                    <span className="text-[10px] text-slate-500 tabular-nums ml-auto">{entry.count}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-72 flex items-center justify-center text-xs text-slate-500">No data</div>
          )}
        </div>
      </div>

      {/* Charts Row 2: Priority + Sentiment */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Priority Radar */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Priority Radar
          </h3>
          {overview.priority_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={overview.priority_distribution}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis
                  dataKey="priority"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                />
                <PolarRadiusAxis tick={{ fill: "#64748b", fontSize: 9 }} />
                <Radar
                  name="Tickets"
                  dataKey="count"
                  stroke="#6366f1"
                  fill="#6366f1"
                  fillOpacity={0.3}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "12px",
                    fontSize: "11px",
                    color: "#e2e8f0",
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-72 flex items-center justify-center text-xs text-slate-500">No data</div>
          )}
        </div>

        {/* AI Sentiment */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-400" />
            AI Sentiment Distribution
          </h3>
          {overview.sentiment_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={overview.sentiment_distribution}
                layout="vertical"
                margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={{ stroke: "#334155" }} />
                <YAxis
                  type="category"
                  dataKey="sentiment"
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  width={80}
                  axisLine={{ stroke: "#334155" }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "12px",
                    fontSize: "11px",
                    color: "#e2e8f0",
                  }}
                />
                <Bar dataKey="count" name="Tickets" fill="#a855f7" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-72 flex items-center justify-center text-xs text-slate-500">No data</div>
          )}
        </div>
      </div>

      {/* HITL Proposal Stats */}
      {Object.keys(overview.proposal_status_counts).length > 0 && (
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            Human-in-the-Loop Proposal Overview
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {["pending", "approved", "rejected", "executed", "expired"].map((status) => {
              const count = overview.proposal_status_counts[status] || 0;
              const colors: Record<string, string> = {
                pending: "text-amber-400 border-amber-500/30 bg-amber-500/5",
                approved: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5",
                rejected: "text-rose-400 border-rose-500/30 bg-rose-500/5",
                executed: "text-indigo-400 border-indigo-500/30 bg-indigo-500/5",
                expired: "text-slate-400 border-slate-500/30 bg-slate-500/5",
              };
              return (
                <div key={status} className={`rounded-lg p-3 border ${colors[status]}`}>
                  <div className="text-[10px] uppercase tracking-wider opacity-60 mb-1">{status}</div>
                  <div className="text-xl font-bold tabular-nums">{count}</div>
                </div>
              );
            })}
          </div>
          <div className="mt-4">
            <Link
              href="/approvals"
              className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
            >
              View Approval Queue <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
