"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import { api, AnalyticsOverview } from "@/lib/api";
import {
  Sparkles,
  Loader2,
  ArrowRight,
  BarChart2,
  TrendingUp,
  Inbox,
  ShieldAlert,
  CheckCircle2,
  Clock,
  AlertTriangle,
  FileText,
  Activity,
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

const PRIORITY_COLORS: Record<string, string> = {
  low: "#6b7280",
  medium: "#3b82f6",
  high: "#f59e0b",
  urgent: "#ef4444",
};

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "#22c55e",
  neutral: "#6366f1",
  negative: "#f59e0b",
  angry: "#ef4444",
  frustrated: "#e879f9",
};

export default function DashboardPage() {
  const { user, activeWorkspace } = useAuth();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [recentTickets, setRecentTickets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [analyticsData, ticketList] = await Promise.all([
          api.analytics.overview(),
          api.tickets.list({ page: 1, page_size: 8, sort_by: "created_at", sort_order: "desc" }),
        ]);
        setOverview(analyticsData);
        setRecentTickets(ticketList.items || []);
      } catch (err: any) {
        setError(err.message || "Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [activeWorkspace?.workspace_id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex items-center gap-3 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
          <span className="text-sm font-medium">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto py-20 text-center">
        <div className="glass-card rounded-2xl p-8 border border-slate-800">
          <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-white mb-2">Dashboard Error</h3>
          <p className="text-xs text-slate-400 mb-4">{error}</p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all"
          >
            Re-authenticate
          </Link>
        </div>
      </div>
    );
  }

  if (!overview) return null;

  const kpiCards = [
    {
      label: "Total Tickets",
      value: overview.total_tickets,
      icon: Inbox,
      color: "text-white",
      accent: "text-slate-400",
      sub: "All-time workspace tickets",
    },
    {
      label: "Open",
      value: overview.open_tickets,
      icon: Clock,
      color: "text-emerald-400",
      accent: "text-emerald-400/60",
      sub: "Awaiting first response",
    },
    {
      label: "In Progress",
      value: overview.in_progress_tickets,
      icon: Activity,
      color: "text-blue-400",
      accent: "text-blue-400/60",
      sub: "Being handled",
    },
    {
      label: "Escalated",
      value: overview.escalated_tickets,
      icon: AlertTriangle,
      color: "text-red-400",
      accent: "text-red-400/60",
      sub: "Flagged for human review",
    },
    {
      label: "Pending Approval",
      value: overview.pending_proposals,
      icon: ShieldAlert,
      color: "text-amber-400",
      accent: "text-amber-400/60",
      sub: "HITL proposals awaiting",
    },
    {
      label: "Resolved",
      value: overview.resolved_tickets,
      icon: CheckCircle2,
      color: "text-emerald-400",
      accent: "text-emerald-400/60",
      sub: "Successfully closed",
    },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="glass-card rounded-2xl p-6 border border-slate-800">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-1">
              <Sparkles className="w-3 h-3" /> Phase 6: Analytics & Integrations
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Welcome back, {user?.full_name}
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              You are authenticated into the{" "}
              <span className="text-white font-medium">
                {activeWorkspace?.workspace_name}
              </span>{" "}
              workspace. All queries are strictly isolated by workspace context.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/tickets"
              className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all shadow-md shadow-indigo-600/20 flex items-center gap-1.5"
            >
              <Inbox className="w-3 h-3" /> Open Inbox
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpiCards.map((card) => {
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
                <Icon className={`w-3.5 h-3.5 ${card.accent}`} />
              </div>
              <div className={`text-2xl font-bold ${card.color} tabular-nums`}>
                {card.value}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">{card.sub}</div>
            </div>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-indigo-400" />
            Ticket Status Distribution
          </h3>
          {overview.status_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
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
            <div className="h-64 flex items-center justify-center text-xs text-slate-500">
              No ticket data yet
            </div>
          )}
        </div>

        {/* Category Distribution */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Category Breakdown
          </h3>
          {overview.category_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={overview.category_distribution}
                layout="vertical"
                margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={{ stroke: "#334155" }} />
                <YAxis
                  type="category"
                  dataKey="category"
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  tickFormatter={(v: string) => v.replace(/_/g, " ")}
                  width={100}
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
                <Bar dataKey="count" name="Tickets" fill="#22c55e" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-xs text-slate-500">
              No category data yet
            </div>
          )}
        </div>
      </div>

      {/* Second Charts Row: Priority + Sentiment */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Priority Distribution */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Priority Distribution
          </h3>
          {overview.priority_distribution.length > 0 ? (
            <div className="flex items-center justify-center h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={overview.priority_distribution}
                    dataKey="count"
                    nameKey="priority"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    innerRadius={40}
                    paddingAngle={3}
                    label={({ priority, count }: any) => `${priority}: ${count}`}
                    labelLine={{ stroke: "#475569", strokeWidth: 1 }}
                  >
                    {overview.priority_distribution.map((entry, index) => (
                      <Cell key={index} fill={PRIORITY_COLORS[entry.priority] || "#6366f1"} />
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
            </div>
          ) : (
            <div className="h-56 flex items-center justify-center text-xs text-slate-500">
              No priority data yet
            </div>
          )}
        </div>

        {/* AI Sentiment */}
        <div className="glass-card rounded-xl p-6 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-400" />
            AI Sentiment Analysis
          </h3>
          {overview.sentiment_distribution.length > 0 ? (
            <div className="space-y-3 pt-2">
              {overview.sentiment_distribution.map((entry) => {
                const total = overview.sentiment_distribution.reduce((a, b) => a + b.count, 0);
                const pct = total > 0 ? Math.round((entry.count / total) * 100) : 0;
                return (
                  <div key={entry.sentiment}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-slate-300 capitalize">
                        {entry.sentiment}
                      </span>
                      <span className="text-[10px] text-slate-400 tabular-nums">
                        {entry.count} ({pct}%)
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: SENTIMENT_COLORS[entry.sentiment] || "#6366f1",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="h-56 flex items-center justify-center text-xs text-slate-500">
              No sentiment data yet
            </div>
          )}
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Proposal Status */}
        {Object.keys(overview.proposal_status_counts).length > 0 && (
          <div className="glass-card rounded-xl p-5 border border-slate-800">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              HITL Proposals
            </h3>
            <div className="space-y-2">
              {Object.entries(overview.proposal_status_counts).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 capitalize">{status}</span>
                  <span className="text-xs font-semibold text-white tabular-nums">{count}</span>
                </div>
              ))}
            </div>
            <Link
              href="/approvals"
              className="mt-3 inline-flex items-center gap-1.5 text-[10px] text-indigo-400 hover:text-indigo-300 font-medium"
            >
              View Queue <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        )}

        {/* Audit Activity */}
        <div className="glass-card rounded-xl p-5 border border-slate-800">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <FileText className="w-4 h-4 text-indigo-400" />
            Audit Activity
          </h3>
          <div className="text-3xl font-bold text-indigo-400 tabular-nums">
            {overview.recent_audit_events_24h}
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Events in last 24 hours</p>
          <Link
            href="/audit"
            className="mt-3 inline-flex items-center gap-1.5 text-[10px] text-indigo-400 hover:text-indigo-300 font-medium"
          >
            View Audit Trail <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {/* Recent Tickets */}
        <div className="glass-card rounded-xl p-5 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Inbox className="w-4 h-4 text-cyan-400" />
              Recent Tickets
            </h3>
            <Link
              href="/tickets"
              className="text-[10px] text-indigo-400 hover:text-indigo-300 font-medium"
            >
              View All
            </Link>
          </div>
          {recentTickets.length === 0 ? (
            <p className="text-xs text-slate-500">
              No tickets yet.{" "}
              <Link href="/tickets" className="text-indigo-400 hover:text-indigo-300">
                Create one
              </Link>
            </p>
          ) : (
            <div className="space-y-2">
              {recentTickets.slice(0, 5).map((ticket: any) => (
                <Link
                  key={ticket.id}
                  href={`/tickets/${ticket.id}`}
                  className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-slate-800/50 transition-colors group"
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: STATUS_COLORS[ticket.status] || "#6b7280" }}
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium text-white block truncate group-hover:text-indigo-300 transition-colors">
                      {ticket.subject}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      #{ticket.ticket_number} · {ticket.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <ArrowRight className="w-3 h-3 text-slate-600 group-hover:text-indigo-400 transition-colors" />
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}