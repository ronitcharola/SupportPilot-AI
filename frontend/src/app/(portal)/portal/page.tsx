"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api, Ticket } from "@/lib/api";
import { useToast } from "@/components/toast";
import {
  LifeBuoy,
  Plus,
  ArrowRight,
  Mail,
  User,
  Clock,
  AlertCircle,
  Loader2,
  CheckCircle2,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function CustomerPortalPage() {
  const { success, error: toastError } = useToast();
  const [customerEmail, setCustomerEmail] = useState("customer@acme.com");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New ticket state
  const [showForm, setShowForm] = useState(false);
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("product_questions");
  const [priority, setPriority] = useState("medium");
  const [customerName, setCustomerName] = useState("Charlie Customer");
  const [submitting, setSubmitting] = useState(false);

  const fetchCustomerTickets = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.portal.list(customerEmail, "acme-corp");
      setTickets(data);
    } catch (err: any) {
      const message = err?.message || "Failed to load customer tickets.";
      setError(message);
      toastError("Could not load your requests", message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomerTickets();
  }, [customerEmail]);

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const created = await api.portal.create(
        {
          subject,
          description,
          category,
          priority,
          customer_email: customerEmail,
          customer_name: customerName,
        },
        "acme-corp"
      );
      setSubject("");
      setDescription("");
      setShowForm(false);
      success(`Request #${created.ticket_number} submitted`, "Our support team will review it shortly.");
      await fetchCustomerTickets();
    } catch (err: any) {
      toastError("Submission failed", err?.message || "Please check the form and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "open":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "in_progress":
        return "bg-sky-500/10 text-sky-400 border-sky-500/30";
      case "pending_approval":
      case "waiting_for_customer":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "resolved":
        return "bg-slate-600/10 text-slate-400 border-slate-600/30";
      default:
        return "bg-slate-700 text-slate-300";
    }
  };

  return (
    <div className="space-y-8">
      {/* Hero Welcome */}
      <div className="glass-card rounded-3xl p-8 border border-slate-800 text-center relative overflow-hidden">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-600/20 text-indigo-400 mb-3 border border-indigo-500/30">
          <LifeBuoy className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight">How can we assist you today?</h1>
        <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
          Submit support inquiries, track existing requests, and communicate with the Acme Corp team.
        </p>

        {/* Customer Email Bar */}
        <div className="mt-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs">
          <Mail className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-slate-400">Viewing tickets for:</span>
          <input
            type="email"
            value={customerEmail}
            onChange={(e) => setCustomerEmail(e.target.value)}
            className="bg-transparent text-white font-medium focus:outline-none border-b border-indigo-500/40 text-xs"
          />
        </div>

        <div className="mt-4 flex justify-center">
          <Link
            href={`/portal/chat?email=${encodeURIComponent(customerEmail)}`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            <span>Ask the AI assistant — instant answers with sources</span>
          </Link>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-white">Your Support Requests ({tickets.length})</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 flex items-center gap-1.5 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>{showForm ? "Close Form" : "Submit New Ticket"}</span>
        </button>
      </div>

      {/* Ticket Submission Form */}
      {showForm && (
        <div className="glass-card rounded-2xl p-6 border border-slate-700 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white">Submit a Support Request</h3>
          <form onSubmit={handleCreateTicket} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Your Full Name</label>
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="product_questions">Product Questions</option>
                  <option value="billing">Billing & Invoices</option>
                  <option value="shipping">Shipping & Orders</option>
                  <option value="technical_issues">Technical Support</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
                placeholder="Brief summary of your question..."
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                rows={4}
                placeholder="Explain the issue or question in detail..."
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 shadow-md shadow-indigo-600/20 disabled:opacity-50"
              >
                {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Submit Ticket</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Ticket List */}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="py-16 flex flex-col items-center justify-center gap-2 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
          <span className="text-xs">Loading support requests...</span>
        </div>
      ) : tickets.length === 0 ? (
        <div className="glass-card rounded-2xl p-10 text-center border border-slate-800">
          <LifeBuoy className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-white">No tickets submitted yet</h4>
          <p className="text-xs text-slate-400 mt-1">Submit your first inquiry above to receive support.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tickets.map((t) => (
            <Link
              key={t.id}
              href={`/portal/tickets/${t.id}?email=${encodeURIComponent(customerEmail)}`}
              className="block glass-card rounded-2xl p-5 border border-slate-800 hover:border-indigo-500/40 hover:bg-slate-900/40 transition-all group"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                      #{t.ticket_number}
                    </span>
                    <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${getStatusBadge(t.status)}`}>
                      {t.status.replace("_", " ")}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-white group-hover:text-indigo-300 transition-colors truncate">
                    {t.subject}
                  </h3>
                  <p className="text-xs text-slate-400 truncate max-w-lg">{t.description}</p>
                </div>

                <div className="flex items-center gap-4 text-xs text-slate-400 flex-shrink-0">
                  <div className="text-right">
                    <span className="text-[10px] text-slate-500 font-mono block">
                      {new Date(t.created_at).toLocaleDateString()}
                    </span>
                    <span className="text-indigo-400 font-medium flex items-center gap-1 justify-end mt-0.5">
                      <MessageSquare className="w-3 h-3" />
                      <span>{t.messages.length} messages</span>
                    </span>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
