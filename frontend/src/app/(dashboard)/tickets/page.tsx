"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import { api, Ticket, TeamMember } from "@/lib/api";
import { useToast } from "@/components/toast";
import {
  Inbox,
  Search,
  Plus,
  User,
  Sparkles,
  ArrowRight,
  AlertCircle,
  Loader2,
  X,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";

const SORT_OPTIONS = [
  { value: "created_at:desc", label: "Newest first" },
  { value: "created_at:asc", label: "Oldest first" },
  { value: "updated_at:desc", label: "Recently updated" },
  { value: "priority:desc", label: "Priority: urgent first" },
  { value: "priority:asc", label: "Priority: low first" },
  { value: "ticket_number:desc", label: "Ticket # descending" },
  { value: "subject:asc", label: "Subject A–Z" },
];

const STATUS_TABS = [
  { label: "All Tickets", value: "" },
  { label: "Open", value: "open" },
  { label: "In Progress", value: "in_progress" },
  { label: "Pending Approval", value: "pending_approval" },
  { label: "Waiting Customer", value: "waiting_for_customer" },
  { label: "Escalated", value: "escalated" },
  { label: "Resolved", value: "resolved" },
  { label: "Closed", value: "closed" },
];

const CATEGORY_OPTIONS = [
  { value: "", label: "All Categories" },
  { value: "billing", label: "Billing" },
  { value: "refunds", label: "Refunds" },
  { value: "technical_issues", label: "Technical Issues" },
  { value: "account_access", label: "Account Access" },
  { value: "orders", label: "Orders" },
  { value: "shipping", label: "Shipping" },
  { value: "product_questions", label: "Product Questions" },
  { value: "other", label: "Other" },
];

const PRIORITY_OPTIONS = [
  { value: "", label: "All Priorities" },
  { value: "urgent", label: "Urgent" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

function TicketListSkeleton() {
  return (
    <div className="space-y-3" aria-hidden="true">
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="glass-card rounded-2xl p-5 border border-slate-800 animate-pulse">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 space-y-2">
              <div className="flex gap-2">
                <div className="h-4 w-16 rounded bg-slate-800" />
                <div className="h-4 w-20 rounded-full bg-slate-800" />
                <div className="h-4 w-16 rounded-full bg-slate-800" />
              </div>
              <div className="h-3.5 w-2/3 rounded bg-slate-800" />
              <div className="h-3 w-1/2 rounded bg-slate-800/70" />
            </div>
            <div className="flex gap-4">
              <div className="h-8 w-32 rounded bg-slate-800/70" />
              <div className="h-8 w-24 rounded bg-slate-800/70" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TicketInboxPage() {
  const { activeWorkspace } = useAuth();
  const { success, error: toastError } = useToast();

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [members, setMembers] = useState<TeamMember[]>([]);

  // Filters
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [selectedPriority, setSelectedPriority] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedAssignee, setSelectedAssignee] = useState("");
  const [sort, setSort] = useState("created_at:desc");
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [escalatedOnly, setEscalatedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // New ticket modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newSubject, setNewSubject] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPriority, setNewPriority] = useState("medium");
  const [newCategory, setNewCategory] = useState("product_questions");
  const [custEmail, setCustEmail] = useState("");
  const [custName, setCustName] = useState("");
  const [creating, setCreating] = useState(false);

  const [sortBy, sortOrder] = sort.split(":") as [
    "created_at" | "updated_at" | "priority" | "ticket_number" | "subject",
    "asc" | "desc"
  ];

  const fetchTickets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.tickets.list({
        status: selectedStatus || undefined,
        priority: selectedPriority || undefined,
        category: selectedCategory || undefined,
        search: search || undefined,
        assignee_id: selectedAssignee || undefined,
        assigned_to_me: assignedToMe,
        escalated: escalatedOnly,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      });
      setTickets(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      const message = err?.message || "Failed to load tickets.";
      setError(message);
      toastError("Could not load tickets", message);
    } finally {
      setLoading(false);
    }
  }, [
    selectedStatus,
    selectedPriority,
    selectedCategory,
    selectedAssignee,
    assignedToMe,
    escalatedOnly,
    search,
    sortBy,
    sortOrder,
    page,
    activeWorkspace?.workspace_id,
    toastError,
  ]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  useEffect(() => {
    api.workspaces
      .getMembers()
      .then(setMembers)
      .catch(() => setMembers([]));
  }, [activeWorkspace?.workspace_id]);

  const resetFilters = () => {
    setSearchInput("");
    setSearch("");
    setSelectedStatus("");
    setSelectedPriority("");
    setSelectedCategory("");
    setSelectedAssignee("");
    setAssignedToMe(false);
    setEscalatedOnly(false);
    setSort("created_at:desc");
    setPage(1);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput.trim());
    setPage(1);
  };

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const created = await api.tickets.create({
        subject: newSubject,
        description: newDesc,
        priority: newPriority,
        category: newCategory,
        customer_email: custEmail || "customer@acme.com",
        customer_name: custName || "Charlie Customer",
      });
      setIsModalOpen(false);
      setNewSubject("");
      setNewDesc("");
      success(`Ticket #${created.ticket_number} created`, "The customer has been recorded and the ticket is in the inbox.");
      await fetchTickets();
    } catch (err: any) {
      toastError("Ticket creation failed", err?.message || "Please review the form and try again.");
    } finally {
      setCreating(false);
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case "urgent":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "high":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "medium":
        return "bg-indigo-500/10 text-indigo-400 border-indigo-500/30";
      default:
        return "bg-slate-500/10 text-slate-400 border-slate-500/30";
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "open":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "in_progress":
        return "bg-sky-500/10 text-sky-400 border-sky-500/30";
      case "pending_approval":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "waiting_for_customer":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "escalated":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "resolved":
        return "bg-slate-600/10 text-slate-400 border-slate-600/30";
      case "closed":
        return "bg-slate-800 text-slate-500 border-slate-700";
      default:
        return "bg-slate-700 text-slate-300";
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Inbox className="w-6 h-6 text-indigo-400" aria-hidden="true" />
            <span>Unified Ticket Inbox</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Multi-tenant ticketing for <span className="text-white font-medium">{activeWorkspace?.workspace_name}</span>.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/portal"
            target="_blank"
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <span>Customer Portal</span>
            <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
          </Link>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 flex items-center gap-1.5 transition-all"
          >
            <Plus className="w-4 h-4" aria-hidden="true" />
            <span>New Ticket</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-card rounded-2xl p-4 border border-slate-800 space-y-4">
        {/* Status Tabs */}
        <div
          role="tablist"
          aria-label="Filter by ticket status"
          className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none border-b border-slate-800/80"
        >
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              role="tab"
              aria-selected={selectedStatus === tab.value}
              onClick={() => {
                setSelectedStatus(tab.value);
                setPage(1);
              }}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                selectedStatus === tab.value
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          {/* Search Box */}
          <form onSubmit={handleSearchSubmit} className="md:col-span-4 relative">
            <label htmlFor="ticket-search" className="sr-only">
              Search tickets
            </label>
            <Search
              className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2"
              aria-hidden="true"
            />
            <input
              id="ticket-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search subject, description or customer..."
              className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
          </form>

          {/* Priority */}
          <div className="md:col-span-2">
            <label htmlFor="filter-priority" className="sr-only">
              Filter by priority
            </label>
            <select
              id="filter-priority"
              value={selectedPriority}
              onChange={(e) => {
                setSelectedPriority(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* Category */}
          <div className="md:col-span-2">
            <label htmlFor="filter-category" className="sr-only">
              Filter by category
            </label>
            <select
              id="filter-category"
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* Assignee */}
          <div className="md:col-span-2">
            <label htmlFor="filter-assignee" className="sr-only">
              Filter by assignee
            </label>
            <select
              id="filter-assignee"
              value={selectedAssignee}
              onChange={(e) => {
                setSelectedAssignee(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              <option value="">All Assignees</option>
              {members.map((member) => (
                <option key={member.user_id} value={member.user_id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </div>

          {/* Sort */}
          <div className="md:col-span-2">
            <label htmlFor="filter-sort" className="sr-only">
              Sort tickets
            </label>
            <select
              id="filter-sort"
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={assignedToMe}
              onChange={(e) => {
                setAssignedToMe(e.target.checked);
                setSelectedAssignee("");
                setPage(1);
              }}
              className="w-4 h-4 rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500"
            />
            <span>Assigned to me</span>
          </label>

          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={escalatedOnly}
              onChange={(e) => {
                setEscalatedOnly(e.target.checked);
                setPage(1);
              }}
              className="w-4 h-4 rounded bg-slate-900 border-slate-700 text-rose-600 focus:ring-rose-500"
            />
            <span className="flex items-center gap-1">
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" aria-hidden="true" />
              Escalated only
            </span>
          </label>

          <button
            type="button"
            onClick={resetFilters}
            className="text-[11px] font-semibold text-slate-400 hover:text-white underline underline-offset-2"
          >
            Reset filters
          </button>
        </div>
      </div>

      {/* Ticket List */}
      {error && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between gap-2"
        >
          <span className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </span>
          <button
            type="button"
            onClick={() => fetchTickets()}
            className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 font-semibold"
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <TicketListSkeleton />
      ) : tickets.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 text-center border border-slate-800">
          <Inbox className="w-10 h-10 text-slate-600 mx-auto mb-3" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-white">No tickets match criteria</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Try adjusting your search terms or filters, or create a new ticket for this workspace.
          </p>
          <div className="mt-4 flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={resetFilters}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold"
            >
              Clear filters
            </button>
            <button
              type="button"
              onClick={() => setIsModalOpen(true)}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
            >
              New ticket
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-slate-400 px-1 font-medium">
            Showing {tickets.length} of {total} tickets
          </div>
          <ul className="space-y-3">
            {tickets.map((t) => (
              <li key={t.id}>
                <Link
                  href={`/tickets/${t.id}`}
                  className="block glass-card rounded-2xl p-5 border border-slate-800 hover:border-indigo-500/40 hover:bg-slate-900/40 transition-all group relative overflow-hidden"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                          #{t.ticket_number}
                        </span>
                        <span
                          className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${getStatusBadge(t.status)}`}
                        >
                          {t.status.replace(/_/g, " ")}
                        </span>
                        <span
                          className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${getPriorityBadge(t.priority)}`}
                        >
                          {t.priority}
                        </span>
                        {t.category && (
                          <span className="text-[10px] font-medium text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60 capitalize">
                            {t.category.replace(/_/g, " ")}
                          </span>
                        )}
                        {t.status === "pending_approval" && (
                          <span className="flex items-center gap-1 text-[10px] font-semibold uppercase text-amber-400">
                            <ShieldAlert className="w-3 h-3" aria-hidden="true" />
                            Awaiting approval
                          </span>
                        )}
                        {t.is_escalated && t.status !== "pending_approval" && (
                          <span className="text-[10px] font-semibold uppercase text-rose-400">Escalated</span>
                        )}
                      </div>

                      <h3 className="text-sm font-semibold text-white group-hover:text-indigo-300 transition-colors truncate">
                        {t.subject}
                      </h3>

                      {t.ai_summary && (
                        <div className="flex items-center gap-1.5 text-xs text-slate-400">
                          <Sparkles className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" aria-hidden="true" />
                          <span className="truncate italic">{t.ai_summary}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-slate-400 flex-shrink-0">
                      <div className="text-right">
                        <div className="text-slate-300 font-medium">{t.customer_name}</div>
                        <div className="text-[11px] text-slate-500">{t.customer_email}</div>
                      </div>

                      <div className="h-8 w-px bg-slate-800 hidden sm:block" />

                      <div className="min-w-28">
                        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Assignee</div>
                        <div className="text-xs font-medium text-white truncate">
                          {t.assigned_agent_name ? (
                            <span className="flex items-center gap-1.5 text-indigo-300">
                              <User className="w-3 h-3" aria-hidden="true" />
                              <span>{t.assigned_agent_name}</span>
                            </span>
                          ) : (
                            <span className="text-slate-500 italic">Unassigned</span>
                          )}
                        </div>
                      </div>

                      <ArrowRight
                        className="w-4 h-4 text-slate-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all"
                        aria-hidden="true"
                      />
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>

          {/* Pagination */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-slate-500">
              Page {page} of {Math.max(totalPages, 1)}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1}
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-xs font-semibold disabled:opacity-40 hover:bg-slate-800 flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((current) => current + 1)}
                disabled={totalPages === 0 || page >= totalPages}
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-xs font-semibold disabled:opacity-40 hover:bg-slate-800 flex items-center gap-1"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Ticket Modal */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="new-ticket-title"
        >
          <div className="glass-card rounded-2xl p-6 border border-slate-700 w-full max-w-lg shadow-2xl relative">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <h2 id="new-ticket-title" className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-indigo-400" aria-hidden="true" />
                <span>Create New Ticket</span>
              </h2>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                aria-label="Close dialog"
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>

            <form onSubmit={handleCreateTicket} className="space-y-4">
              <div>
                <label htmlFor="new-subject" className="block text-xs font-medium text-slate-300 mb-1">
                  Subject
                </label>
                <input
                  id="new-subject"
                  type="text"
                  value={newSubject}
                  onChange={(e) => setNewSubject(e.target.value)}
                  required
                  minLength={2}
                  maxLength={255}
                  placeholder="Summary of the issue..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="new-cust-email" className="block text-xs font-medium text-slate-300 mb-1">
                    Customer Email
                  </label>
                  <input
                    id="new-cust-email"
                    type="email"
                    value={custEmail}
                    onChange={(e) => setCustEmail(e.target.value)}
                    placeholder="customer@acme.com"
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label htmlFor="new-cust-name" className="block text-xs font-medium text-slate-300 mb-1">
                    Customer Name
                  </label>
                  <input
                    id="new-cust-name"
                    type="text"
                    value={custName}
                    onChange={(e) => setCustName(e.target.value)}
                    placeholder="Charlie Customer"
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="new-priority" className="block text-xs font-medium text-slate-300 mb-1">
                    Priority
                  </label>
                  <select
                    id="new-priority"
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="new-category" className="block text-xs font-medium text-slate-300 mb-1">
                    Category
                  </label>
                  <select
                    id="new-category"
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {CATEGORY_OPTIONS.filter((option) => option.value).map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="new-description" className="block text-xs font-medium text-slate-300 mb-1">
                  Description / Initial Message
                </label>
                <textarea
                  id="new-description"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  required
                  minLength={5}
                  rows={4}
                  placeholder="Detail the customer's question or issue..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 disabled:opacity-50 flex items-center gap-1.5"
                >
                  {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />}
                  <span>Create Ticket</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
