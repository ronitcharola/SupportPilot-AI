"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import { api, Proposal, ProposalListResponse } from "@/lib/api";
import { useToast } from "@/components/toast";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  AlertCircle,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Lock,
  DollarSign,
  Package,
  Percent,
  Flag,
  Eye,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_TABS = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
  { label: "Executed", value: "executed" },
  { label: "Expired", value: "expired" },
];

const ACTION_LABELS: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  issue_refund: { label: "Issue Refund", icon: DollarSign, color: "text-emerald-400" },
  cancel_order: { label: "Cancel Order", icon: Package, color: "text-red-400" },
  apply_discount: { label: "Apply Discount", icon: Percent, color: "text-blue-400" },
  flag_account: { label: "Flag Account", icon: Flag, color: "text-amber-400" },
};

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  approved: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  rejected: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  executed: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
  expired: "bg-slate-500/10 text-slate-400 border-slate-500/30",
};

function generateIdempotencyKey(): string {
  return `approve-${Date.now()}-${Math.random().toString(36).substring(2, 12)}`;
}

export default function ApprovalsPage() {
  const { activeWorkspace } = useAuth();
  const toast = useToast();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState("");

  const loadProposals = useCallback(async () => {
    setLoading(true);
    try {
      const res: ProposalListResponse = await api.proposals.list({
        status: statusFilter || undefined,
        page,
        page_size: 15,
      });
      setProposals(res.items);
      setStatusCounts(res.status_counts || {});
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch (err: any) {
      toast.error("Failed to load proposals", err.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page, activeWorkspace?.workspace_id]);

  useEffect(() => {
    loadProposals();
  }, [loadProposals]);

  const handleApprove = async (id: string) => {
    setActionLoading(id);
    try {
      const key = generateIdempotencyKey();
      const updated = await api.proposals.approve(id, {
        idempotency_key: key,
        note: reviewNote || undefined,
      });
      toast.success("Proposal Approved", `Action executed successfully.`);
      setReviewNote("");
      setSelectedProposal(updated);
      await loadProposals();
    } catch (err: any) {
      toast.error("Approval Failed", err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id: string) => {
    setActionLoading(id);
    try {
      const updated = await api.proposals.reject(id, {
        note: reviewNote || undefined,
      });
      toast.success("Proposal Rejected", "The action will not be executed.");
      setReviewNote("");
      setSelectedProposal(updated);
      await loadProposals();
    } catch (err: any) {
      toast.error("Rejection Failed", err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
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
          <ShieldAlert className="w-6 h-6 text-amber-400" />
          AI Action Approval Queue
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Human-in-the-loop review of consequential AI-proposed actions. All approvals are
          idempotent, role-validated server-side, and produce immutable audit records.
        </p>
      </div>

      {/* Architecture Banner */}
      <div className="glass-card rounded-xl p-4 border border-amber-500/20 bg-amber-950/10">
        <div className="flex items-start gap-3">
          <Lock className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-slate-300 space-y-1">
            <span className="font-semibold text-amber-300">HITL Safety Guarantees:</span>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-400">
              <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-amber-400/60" /> Server-side RBAC re-validation</span>
              <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-amber-400/60" /> Idempotency key deduplication</span>
              <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-amber-400/60" /> Atomic status transitions</span>
              <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-amber-400/60" /> Immutable audit trail</span>
            </div>
          </div>
        </div>
      </div>

      {/* Status Tabs */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {STATUS_TABS.map((tab) => {
          const count = tab.value ? statusCounts[tab.value] || 0 : total;
          return (
            <button
              key={tab.value}
              onClick={() => { setStatusFilter(tab.value); setPage(1); }}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5",
                statusFilter === tab.value
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                  : "bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-800"
              )}
            >
              {tab.label}
              <span className={cn(
                "text-[10px] px-1.5 py-0.5 rounded-full font-semibold",
                statusFilter === tab.value
                  ? "bg-white/20 text-white"
                  : "bg-slate-700 text-slate-400"
              )}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Proposal List */}
        <div className="lg:col-span-2 space-y-3">
          {loading ? (
            <div className="glass-card rounded-xl p-12 border border-slate-800 flex items-center justify-center gap-2 text-slate-400 text-xs">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              Loading proposals...
            </div>
          ) : proposals.length === 0 ? (
            <div className="glass-card rounded-xl p-12 border border-slate-800 text-center">
              <ShieldAlert className="w-8 h-8 text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-400">No proposals found</p>
              <p className="text-[10px] text-slate-500 mt-1">
                AI-proposed actions will appear here when created from ticket triage.
              </p>
            </div>
          ) : (
            proposals.map((p) => {
              const actionInfo = ACTION_LABELS[p.action_type] || {
                label: p.action_type,
                icon: Sparkles,
                color: "text-slate-400",
              };
              const ActionIcon = actionInfo.icon;
              const isSelected = selectedProposal?.id === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => { setSelectedProposal(p); setReviewNote(""); }}
                  className={cn(
                    "w-full text-left glass-card rounded-xl p-4 border transition-all",
                    isSelected
                      ? "border-indigo-500/50 shadow-lg shadow-indigo-500/5"
                      : "border-slate-800 hover:border-slate-700"
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0", `${actionInfo.color.replace("text-", "bg-")}/10`)}>
                        <ActionIcon className={cn("w-4 h-4", actionInfo.color)} />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-xs font-semibold text-white">{actionInfo.label}</span>
                          <span className={cn("text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded-full border", STATUS_STYLES[p.status] || STATUS_STYLES.pending)}>
                            {p.status}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 truncate">
                          {p.ticket_subject ? `Ticket #${p.ticket_number}: ${p.ticket_subject}` : `Ticket ${p.ticket_id.slice(0, 8)}…`}
                        </p>
                        <p className="text-[10px] text-slate-500 mt-1 line-clamp-2">{p.rationale}</p>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-[10px] text-slate-500">{formatDate(p.created_at)}</div>
                      {p.ai_confidence !== null && (
                        <div className="text-[10px] text-indigo-400 mt-0.5">
                          {Math.round(p.ai_confidence * 100)}% confidence
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Params preview */}
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(p.params).slice(0, 4).map(([k, v]) => (
                      <span key={k} className="text-[9px] bg-slate-800/80 text-slate-400 px-2 py-0.5 rounded-md border border-slate-700/50 font-mono">
                        {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </span>
                    ))}
                  </div>
                </button>
              );
            })
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
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

        {/* Detail / Action Panel */}
        <div className="lg:col-span-1">
          {selectedProposal ? (
            <div className="glass-card rounded-xl p-5 border border-slate-800 sticky top-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white">Proposal Detail</h3>
                <span className={cn(
                  "text-[9px] font-semibold uppercase px-2 py-0.5 rounded-full border",
                  STATUS_STYLES[selectedProposal.status] || STATUS_STYLES.pending
                )}>
                  {selectedProposal.status}
                </span>
              </div>

              {/* Action Type */}
              <div>
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Action</span>
                <p className="text-xs font-medium text-white mt-0.5">
                  {ACTION_LABELS[selectedProposal.action_type]?.label || selectedProposal.action_type}
                </p>
              </div>

              {/* Linked Ticket */}
              <div>
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Ticket</span>
                <Link
                  href={`/tickets/${selectedProposal.ticket_id}`}
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mt-0.5"
                >
                  #{selectedProposal.ticket_number} — {selectedProposal.ticket_subject || "View"}
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>

              {/* Rationale */}
              <div>
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Rationale</span>
                <p className="text-xs text-slate-300 mt-0.5">{selectedProposal.rationale}</p>
              </div>

              {/* Parameters */}
              <div>
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Parameters</span>
                <div className="mt-1 space-y-1">
                  {Object.entries(selectedProposal.params).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between text-xs">
                      <span className="text-slate-400 font-mono">{k}</span>
                      <span className="text-white font-semibold">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Policy */}
              <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Approval Policy</span>
                <div className="mt-1 space-y-1 text-xs">
                  {selectedProposal.policy.requires_admin && (
                    <div className="flex items-center gap-1.5 text-amber-400">
                      <Lock className="w-3 h-3" />
                      <span>Requires Admin approval</span>
                    </div>
                  )}
                  {selectedProposal.policy.note && (
                    <p className="text-slate-400">{selectedProposal.policy.note}</p>
                  )}
                  {selectedProposal.policy.agent_limit !== null && (
                    <p className="text-slate-400">
                      Agent limit: ${selectedProposal.policy.agent_limit}
                    </p>
                  )}
                </div>
              </div>

              {/* AI Confidence */}
              {selectedProposal.ai_confidence !== null && (
                <div>
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">AI Confidence</span>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-indigo-500 transition-all"
                        style={{ width: `${Math.round(selectedProposal.ai_confidence * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-indigo-400">
                      {Math.round(selectedProposal.ai_confidence * 100)}%
                    </span>
                  </div>
                </div>
              )}

              {/* Reviewer info */}
              {selectedProposal.reviewed_by_name && (
                <div>
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">Reviewed By</span>
                  <p className="text-xs text-white mt-0.5">{selectedProposal.reviewed_by_name}</p>
                  {selectedProposal.reviewed_at && (
                    <p className="text-[10px] text-slate-500">{formatDate(selectedProposal.reviewed_at)}</p>
                  )}
                  {selectedProposal.reviewer_note && (
                    <p className="text-xs text-slate-400 mt-1 italic">&quot;{selectedProposal.reviewer_note}&quot;</p>
                  )}
                </div>
              )}

              {/* Execution result */}
              {selectedProposal.execution_result && (
                <div>
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">Execution Result</span>
                  <pre className="mt-1 p-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-[10px] text-emerald-300 font-mono overflow-x-auto">
                    {JSON.stringify(selectedProposal.execution_result, null, 2)}
                  </pre>
                </div>
              )}

              {/* Actions — only for pending */}
              {selectedProposal.status === "pending" && (
                <div className="space-y-3 pt-2 border-t border-slate-800">
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
                      Review Note (optional)
                    </label>
                    <textarea
                      value={reviewNote}
                      onChange={(e) => setReviewNote(e.target.value)}
                      placeholder="Add context for the audit trail..."
                      className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-white text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 resize-none"
                      rows={2}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleApprove(selectedProposal.id)}
                      disabled={actionLoading === selectedProposal.id}
                      className="flex-1 py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all disabled:opacity-50 shadow-md shadow-emerald-600/20"
                    >
                      {actionLoading === selectedProposal.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      )}
                      Approve & Execute
                    </button>
                    <button
                      onClick={() => handleReject(selectedProposal.id)}
                      disabled={actionLoading === selectedProposal.id}
                      className="flex-1 py-2 px-3 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/30 text-rose-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all disabled:opacity-50"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      Reject
                    </button>
                  </div>
                </div>
              )}

              {/* Expiry */}
              {selectedProposal.expires_at && selectedProposal.status === "pending" && (
                <div className="text-[10px] text-slate-500 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Expires: {formatDate(selectedProposal.expires_at)}
                </div>
              )}
            </div>
          ) : (
            <div className="glass-card rounded-xl p-8 border border-slate-800 text-center">
              <Eye className="w-6 h-6 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-400">Select a proposal to review</p>
              <p className="text-[10px] text-slate-500 mt-1">
                Click any proposal in the list to view details and take action.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
