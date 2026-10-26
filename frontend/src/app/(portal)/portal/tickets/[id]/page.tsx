"use client";

import React, { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { api, Ticket } from "@/lib/api";
import { useToast } from "@/components/toast";
import {
  ArrowLeft,
  MessageSquare,
  Send,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Clock,
  User,
  Headphones,
} from "lucide-react";
import { cn } from "@/lib/utils";

function CustomerTicketDetailContent() {
  const { id } = useParams() as { id: string };
  const { success, error: toastError } = useToast();
  const searchParams = useSearchParams();
  const emailParam = searchParams.get("email") || "customer@acme.com";

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [sending, setSending] = useState(false);

  const fetchTicket = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.portal.get(id, emailParam, "acme-corp");
      setTicket(data);
    } catch (err: any) {
      const message = err?.message || "Failed to load support request.";
      setError(message);
      toastError("Could not load your request", message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id && emailParam) {
      fetchTicket();
    }
  }, [id, emailParam]);

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyBody.trim() || !ticket) return;
    setSending(true);
    try {
      await api.portal.addMessage(ticket.id, { body: replyBody }, emailParam, "acme-corp");
      setReplyBody("");
      await fetchTicket();
      success("Message sent", "The support team has been notified.");
    } catch (err: any) {
      toastError("Message not sent", err?.message || "Failed to post message.");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        <span className="text-xs">Loading support inquiry...</span>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-md mx-auto py-16 text-center space-y-4">
        <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
        <h2 className="text-base font-bold text-white">Inquiry Not Found</h2>
        <p className="text-xs text-slate-400">{error || "Could not retrieve ticket details."}</p>
        <Link
          href={`/portal?email=${encodeURIComponent(emailParam)}`}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-800 text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Return to Portal</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Navigation */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Link
            href={`/portal?email=${encodeURIComponent(emailParam)}`}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors border border-slate-800"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                #{ticket.ticket_number}
              </span>
              <span className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 uppercase text-[10px]">
                {ticket.status.replace("_", " ")}
              </span>
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight mt-1">{ticket.subject}</h1>
          </div>
        </div>
      </div>

      {/* Messages Thread */}
      <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 pb-2 border-b border-slate-800">
          <MessageSquare className="w-4 h-4" />
          <span>Message Thread ({ticket.messages.length})</span>
        </h2>

        <div className="space-y-4 pt-1">
          {ticket.messages.map((m) => {
            const isCustomer = m.sender_type === "customer";
            return (
              <div
                key={m.id}
                className={cn(
                  "p-4 rounded-2xl text-xs space-y-1.5",
                  isCustomer
                    ? "bg-slate-900 border border-slate-800 text-slate-200 ml-6"
                    : "bg-indigo-950/40 border border-indigo-500/30 text-white mr-6 shadow-sm"
                )}
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400 pb-1.5 border-b border-white/5">
                  <div className="flex items-center gap-2 font-semibold">
                    {!isCustomer && <Headphones className="w-3.5 h-3.5 text-indigo-400" />}
                    <span className={!isCustomer ? "text-indigo-300" : "text-white"}>{m.sender_name}</span>
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

      {/* Customer Reply Composer */}
      <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-3">
        <h3 className="text-xs font-semibold text-white">Send a Message</h3>
        <form onSubmit={handleSendReply} className="space-y-3">
          <textarea
            value={replyBody}
            onChange={(e) => setReplyBody(e.target.value)}
            rows={3}
            required
            placeholder="Type your message to Acme Corp support..."
            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600"
          />

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={sending || !replyBody.trim()}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 flex items-center gap-2 transition-all disabled:opacity-50"
            >
              {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>Send Message</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function CustomerTicketDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="py-24 flex justify-center items-center text-slate-400 gap-2">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
          <span className="text-xs">Loading inquiry...</span>
        </div>
      }
    >
      <CustomerTicketDetailContent />
    </Suspense>
  );
}
