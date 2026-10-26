"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { api, ChatCitation, Ticket, TeamMember } from "@/lib/api";
import { useToast } from "@/components/toast";
import {
  ArrowLeft,
  User,
  Clock,
  Sparkles,
  ShieldCheck,
  Lock,
  Send,
  AlertCircle,
  Loader2,
  CheckCircle2,
  MessageSquare,
  FileText,
  Building,
  Mail,
  ChevronDown,
  RefreshCw,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  pending_approval: "Pending Approval",
  waiting_for_customer: "Waiting for Customer",
  escalated: "Escalated",
  resolved: "Resolved",
  closed: "Closed",
};

export default function TicketDetailPage() {
  const { id } = useParams() as { id: string };
  const { activeWorkspace } = useAuth();
  const { success, error: toastError, toast } = useToast();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Composer
  const [replyBody, setReplyBody] = useState("");
  const [isInternalNote, setIsInternalNote] = useState(false);
  const [sending, setSending] = useState(false);

  // AI triage
  const [classifying, setClassifying] = useState(false);
  const [applyingAI, setApplyingAI] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [draftCitations, setDraftCitations] = useState<ChatCitation[]>([]);

  const fetchTicketAndMembers = async () => {
    try {
      setLoading(true);
      setError(null);
      const [tData, mData] = await Promise.all([
        api.tickets.get(id),
        api.workspaces.getMembers().catch(() => []),
      ]);
      setTicket(tData);
      setMembers(mData);
    } catch (err: any) {
      setError(err.message || "Failed to load ticket.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      fetchTicketAndMembers();
    }
  }, [id, activeWorkspace?.workspace_id]);

  const handleStatusChange = async (newStatus: string) => {
    if (!ticket || newStatus === ticket.status) return;
    try {
      const updated = await api.tickets.update(ticket.id, { status: newStatus });
      setTicket(updated);
      success("Ticket status updated", `Moved to ${STATUS_LABELS[newStatus] || newStatus}.`);
    } catch (err: any) {
      toastError("Status change rejected", err?.message || "Failed to update status");
    }
  };

  const handlePriorityChange = async (newPriority: string) => {
    if (!ticket) return;
    try {
      const updated = await api.tickets.update(ticket.id, { priority: newPriority });
      setTicket(updated);
      success("Priority updated", `Ticket priority is now ${newPriority}.`);
    } catch (err: any) {
      toastError("Priority update failed", err?.message || "Failed to update priority");
    }
  };

  const handleAssignChange = async (userId: string) => {
    if (!ticket || !userId) return;
    try {
      const updated = await api.tickets.assign(ticket.id, {
        assigned_to_user_id: userId,
        reason: "Assigned via dashboard interface",
      });
      setTicket(updated);
      success("Ticket assigned", `Now owned by ${updated.assigned_agent_name || "the selected agent"}.`);
    } catch (err: any) {
      toastError("Assignment failed", err?.message || "Failed to assign ticket");
    }
  };

  const handleClassify = async (applyFields: boolean) => {
    if (!ticket) return;
    if (applyFields) setApplyingAI(true);
    else setClassifying(true);
    try {
      const updated = await api.tickets.classify(ticket.id, applyFields);
      setTicket(updated);
      if (applyFields) {
        success(
          "AI suggestion applied",
          `Category ${updated.category?.replace("_", " ") || "unchanged"}, priority ${updated.priority}.`
        );
      } else {
        success("Ticket reclassified", updated.ai_summary || "AI triage metadata refreshed.");
      }
    } catch (err: any) {
      toastError("AI triage failed", err?.message || "The provider is unavailable right now.");
    } finally {
      setClassifying(false);
      setApplyingAI(false);
    }
  };

  const handleDraftReply = async () => {
    if (!ticket) return;
    setDrafting(true);
    try {
      const result = await api.tickets.suggestedReply(ticket.id);
      if (result.draft) {
        setReplyBody(result.draft);
        setIsInternalNote(false);
        setDraftCitations(result.citations || []);
        success(
          "Grounded draft ready",
          "Review and edit before sending. Nothing was sent automatically."
        );
      } else {
        setDraftCitations([]);
        toast({
          title: "No grounded draft available",
          description: result.note || "Add knowledge or reply manually.",
          variant: "info",
        });
      }
    } catch (err: any) {
      toastError("Could not draft a reply", err?.message || "The AI provider is unavailable.");
    } finally {
      setDrafting(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyBody.trim() || !ticket) return;
    setSending(true);
    try {
      await api.tickets.addMessage(ticket.id, {
        body: replyBody,
        is_internal_note: isInternalNote,
      });
      setReplyBody("");
      setDraftCitations([]);
      // Refetch full ticket to get populated senders
      const refreshed = await api.tickets.get(ticket.id);
      setTicket(refreshed);
      success(isInternalNote ? "Internal note saved" : "Reply sent", isInternalNote ? "Only your team can see this note." : "The customer can now see your reply.");
    } catch (err: any) {
      toastError("Message not sent", err?.message || "Failed to send message");
    } finally {
      setSending(false);
    }
  };

  const escalationReasons = ticket
    ? ticket.ai_escalation_reasons?.length
      ? ticket.ai_escalation_reasons
      : ticket.escalation_reason
      ? [ticket.escalation_reason]
      : []
    : [];

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        <span className="text-xs">Loading ticket context...</span>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto mb-3" />
        <h2 className="text-base font-bold text-white">Error Loading Ticket</h2>
        <p className="text-xs text-slate-400 mt-1 mb-6">{error || "Ticket not found."}</p>
        <Link
          href="/tickets"
          className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold"
        >
          Back to Inbox
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Breadcrumb & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div className="flex items-center gap-3">
          <Link
            href="/tickets"
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                #{ticket.ticket_number}
              </span>
              <span className="text-xs text-slate-400">· {ticket.category?.replace("_", " ") || "General"}</span>
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight mt-0.5">{ticket.subject}</h1>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Status select */}
          <select
            aria-label="Ticket status"
            value={ticket.status}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 capitalize"
          >
            {/* Only server-approved transitions are offered. */}
            {[ticket.status, ...(ticket.allowed_transitions || []).filter((s) => s !== ticket.status)].map((status) => (
              <option key={status} value={status}>
                Status: {STATUS_LABELS[status] || status}
              </option>
            ))}
          </select>

          {/* Priority select */}
          <select
            aria-label="Ticket priority"
            value={ticket.priority}
            onChange={(e) => handlePriorityChange(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 capitalize"
          >
            <option value="low">Priority: Low</option>
            <option value="medium">Priority: Medium</option>
            <option value="high">Priority: High</option>
            <option value="urgent">Priority: Urgent</option>
          </select>

          {/* Assignee select */}
          <select
            aria-label="Ticket assignee"
            value={ticket.assigned_agent_id || ""}
            onChange={(e) => handleAssignChange(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="" disabled>
              Assign: Unassigned
            </option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                Assign: {m.full_name} ({m.role})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* AI Triage Card */}
      {(ticket.ai_summary || ticket.ai_intent || ticket.is_escalated) && (
        <div className="glass-card rounded-2xl p-4 border border-indigo-500/30 bg-gradient-to-r from-indigo-950/40 to-slate-900/60 relative overflow-hidden">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex-shrink-0">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="space-y-2 min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold text-white tracking-wide">AI Triage</span>
                {ticket.ai_intent && (
                  <span className="text-[10px] font-mono font-semibold uppercase px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    Intent: {ticket.ai_intent}
                  </span>
                )}
                {ticket.ai_sentiment && (
                  <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    {ticket.ai_sentiment}
                  </span>
                )}
                {ticket.ai_confidence != null && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {Math.round(ticket.ai_confidence * 100)}% confidence
                  </span>
                )}
                {ticket.ai_urgency_score != null && (
                  <span
                    className={cn(
                      "text-[10px] font-semibold px-2 py-0.5 rounded border",
                      ticket.ai_urgency_score >= 0.85
                        ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                        : ticket.ai_urgency_score >= 0.6
                        ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                        : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    )}
                  >
                    Urgency {Math.round(ticket.ai_urgency_score * 100)}%
                  </span>
                )}

                <div className="flex items-center gap-1.5 ml-auto">
                  <button
                    type="button"
                    onClick={() => handleClassify(false)}
                    disabled={classifying || applyingAI}
                    className="px-2.5 py-1 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700 text-[10px] font-semibold flex items-center gap-1 disabled:opacity-50"
                  >
                    {classifying ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    <span>Reclassify</span>
                  </button>
                  {ticket.ai_suggested_category && (
                    <button
                      type="button"
                      onClick={() => handleClassify(true)}
                      disabled={classifying || applyingAI}
                      className="px-2.5 py-1 rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-600/30 text-[10px] font-semibold flex items-center gap-1 disabled:opacity-50"
                    >
                      {applyingAI ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                      <span>Apply suggestion</span>
                    </button>
                  )}
                </div>
              </div>

              {ticket.ai_summary && (
                <p className="text-xs text-slate-300 leading-relaxed">{ticket.ai_summary}</p>
              )}

              {(ticket.ai_suggested_category || ticket.ai_suggested_priority) && (
                <p className="text-[11px] text-slate-400">
                  Suggested classification:{" "}
                  <span className="text-indigo-300 font-medium capitalize">
                    {ticket.ai_suggested_category?.replace("_", " ") || "unchanged"}
                  </span>{" "}
                  · priority{" "}
                  <span className="text-indigo-300 font-medium">{ticket.ai_suggested_priority || "unchanged"}</span>
                  <span className="text-slate-500"> (never applied automatically)</span>
                </p>
              )}

              {ticket.is_escalated && (
                <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/25 space-y-1">
                  <p className="text-[11px] font-semibold text-rose-300 flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Flagged for human escalation
                  </p>
                  {escalationReasons.slice(0, 5).map((reason) => (
                    <p key={reason} className="text-[10px] text-rose-200/80 leading-relaxed">
                      · {reason}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Main Grid: Thread on Left, Customer Info on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Conversation Thread */}
        <div className="lg:col-span-8 space-y-4">
          <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 pb-2 border-b border-slate-800">
              <MessageSquare className="w-4 h-4" />
              <span>Conversation History ({ticket.messages.length})</span>
            </h2>

            {/* Messages List */}
            <div className="space-y-4 pt-1">
              {ticket.messages.map((m) => {
                const isAgent = m.sender_type === "agent";
                const isCustomer = m.sender_type === "customer";
                const isNote = m.is_internal_note;

                return (
                  <div
                    key={m.id}
                    className={cn(
                      "p-4 rounded-2xl transition-all text-xs",
                      isNote
                        ? "bg-amber-500/10 border border-amber-500/30 text-amber-200"
                        : isAgent
                        ? "bg-indigo-950/40 border border-indigo-500/20 text-slate-200 ml-4"
                        : "bg-slate-900/80 border border-slate-800 text-slate-200 mr-4"
                    )}
                  >
                    <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/5">
                      <div className="flex items-center gap-2">
                        {isNote ? (
                          <div className="flex items-center gap-1.5 text-amber-400 font-semibold text-[11px]">
                            <Lock className="w-3.5 h-3.5" />
                            <span>Internal Team Note</span>
                          </div>
                        ) : (
                          <span className="font-semibold text-white">{m.sender_name}</span>
                        )}
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                          ({m.sender_type})
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>

                    <div className="whitespace-pre-wrap leading-relaxed">{m.body}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Reply / Note Composer */}
          <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-3">
            {/* Mode Selector + AI Draft */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setIsInternalNote(false)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5",
                  !isInternalNote
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                )}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>Reply to Customer</span>
              </button>
              <button
                type="button"
                onClick={() => setIsInternalNote(true)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5",
                  isInternalNote
                    ? "bg-amber-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                )}
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Add Internal Note</span>
              </button>
              </div>

              <button
                type="button"
                onClick={handleDraftReply}
                disabled={drafting || sending}
                title="Draft a reply grounded in the knowledge base. Nothing is sent automatically."
                className="px-3 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold flex items-center gap-1.5 hover:bg-indigo-500/20 disabled:opacity-50"
              >
                {drafting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                <span>{drafting ? "Drafting..." : "Draft with AI"}</span>
              </button>
            </div>

            <form onSubmit={handleSendMessage} className="space-y-3">
              <textarea
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
                rows={4}
                required
                placeholder={
                  isInternalNote
                    ? "Write an internal team note (hidden from customer)..."
                    : "Draft your customer reply..."
                }
                className={cn(
                  "w-full px-3.5 py-2.5 rounded-xl text-xs text-white focus:outline-none focus:ring-2 transition-all placeholder:text-slate-600",
                  isInternalNote
                    ? "bg-amber-950/20 border border-amber-500/30 focus:ring-amber-500"
                    : "bg-slate-900 border border-slate-700 focus:ring-indigo-500"
                )}
              />

              {draftCitations.length > 0 && (
                <div className="rounded-xl border border-indigo-500/25 bg-indigo-950/20 p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase tracking-wider text-indigo-300 font-semibold">
                      Grounded sources ({draftCitations.length})
                    </span>
                    <button
                      type="button"
                      onClick={() => setDraftCitations([])}
                      aria-label="Clear sources"
                      className="text-slate-400 hover:text-white p-0.5"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {draftCitations.map((citation) => (
                    <div key={`${citation.number}-${citation.chunk_index}`} className="text-[10px] text-slate-400 leading-relaxed">
                      <span className="text-indigo-300 font-semibold">
                        [{citation.number}] {citation.document_title}
                      </span>{" "}
                      <span className="text-slate-500 font-mono">
                        {Math.round(citation.score * 100)}% match
                      </span>
                      <p className="line-clamp-2">{citation.excerpt}</p>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between">
                <div className="text-[11px] text-slate-500">
                  {isInternalNote ? (
                    <span className="text-amber-400/80 flex items-center gap-1">
                      <Lock className="w-3 h-3" /> Note will only be visible to Support Agents & Admins.
                    </span>
                  ) : (
                    <span>Customer will receive an email and portal update.</span>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={sending || !replyBody.trim()}
                  className={cn(
                    "px-4 py-2 rounded-xl text-white text-xs font-semibold shadow-md flex items-center gap-2 transition-all disabled:opacity-50",
                    isInternalNote
                      ? "bg-amber-600 hover:bg-amber-500 shadow-amber-600/20"
                      : "bg-indigo-600 hover:bg-indigo-500 shadow-indigo-600/20"
                  )}
                >
                  {sending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                  <span>{isInternalNote ? "Save Internal Note" : "Send Reply"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Sidebar Metadata */}
        <div className="lg:col-span-4 space-y-4">
          {/* Customer Profile Card */}
          <div className="glass-card rounded-2xl p-5 border border-slate-800 space-y-3">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-indigo-400" />
              <span>Customer Details</span>
            </h3>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">Name</span>
                <span className="text-white font-medium">{ticket.customer_name}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">Email</span>
                <span className="text-slate-300 font-mono text-[11px]">{ticket.customer_email}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">Customer ID</span>
                <span className="text-slate-400 font-mono text-[10px]">{ticket.customer_id}</span>
              </div>
            </div>
          </div>

          {/* Ticket Information */}
          <div className="glass-card rounded-2xl p-5 border border-slate-800 space-y-3">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-indigo-400" />
              <span>Ticket Metadata</span>
            </h3>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center py-1 border-b border-slate-800/80">
                <span className="text-slate-400">Status</span>
                <span className="capitalize font-semibold text-white">{ticket.status.replace("_", " ")}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800/80">
                <span className="text-slate-400">Priority</span>
                <span className="capitalize font-semibold text-white">{ticket.priority}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800/80">
                <span className="text-slate-400">Category</span>
                <span className="capitalize font-semibold text-white">{ticket.category?.replace("_", " ") || "General"}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800/80">
                <span className="text-slate-400">Assigned Agent</span>
                <span className="font-semibold text-white">{ticket.assigned_agent_name || "Unassigned"}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800/80">
                <span className="text-slate-400">Created</span>
                <span className="font-mono text-[11px] text-slate-400">{new Date(ticket.created_at).toLocaleDateString()}</span>
              </div>
              {ticket.resolved_at && (
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-400">Resolved At</span>
                  <span className="font-mono text-[11px] text-emerald-400">{new Date(ticket.resolved_at).toLocaleDateString()}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
