"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { useToast } from "@/components/toast";
import {
  api,
  KnowledgeDocument,
  KnowledgeSearchResponse,
  KnowledgeStats,
} from "@/lib/api";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Database,
  FileText,
  Gauge,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_TABS = [
  { label: "All", value: "" },
  { label: "Indexed", value: "indexed" },
  { label: "Pending", value: "pending" },
  { label: "Processing", value: "processing" },
  { label: "Failed", value: "failed" },
] as const;

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusStyles(status: string): string {
  switch (status) {
    case "indexed":
      return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    case "processing":
      return "bg-sky-500/10 text-sky-400 border-sky-500/30";
    case "pending":
      return "bg-amber-500/10 text-amber-400 border-amber-500/30";
    default:
      return "bg-rose-500/10 text-rose-400 border-rose-500/30";
  }
}

export default function KnowledgePage() {
  const { activeWorkspace } = useAuth();
  const { success, error: toastError } = useToast();
  const isAdmin = activeWorkspace?.role === "admin";

  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);

  const [uploadTitle, setUploadTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [showTextForm, setShowTextForm] = useState(false);
  const [textTitle, setTextTitle] = useState("");
  const [textContent, setTextContent] = useState("");
  const [savingText, setSavingText] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const [previewQuery, setPreviewQuery] = useState("");
  const [preview, setPreview] = useState<KnowledgeSearchResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      setError(null);
      const data = await api.knowledge.list({
        status: statusFilter || undefined,
        search: appliedSearch || undefined,
        page,
        page_size: 10,
      });
      setDocuments(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err: any) {
      const message = err?.message || "Failed to load knowledge documents.";
      setError(message);
      toastError("Knowledge base unavailable", message);
    }
  }, [statusFilter, appliedSearch, page, toastError]);

  const fetchStats = useCallback(async () => {
    try {
      setStats(await api.knowledge.stats());
    } catch {
      // Stats are supplementary; the document list error state is authoritative.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      await Promise.all([fetchDocuments(), fetchStats()]);
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchDocuments, fetchStats]);

  const isProcessing = useMemo(
    () => documents.some((doc) => doc.status === "pending" || doc.status === "processing"),
    [documents]
  );

  useEffect(() => {
    if (!isProcessing) return;
    const timer = setInterval(() => {
      fetchDocuments();
      fetchStats();
    }, 4000);
    return () => clearInterval(timer);
  }, [isProcessing, fetchDocuments, fetchStats]);

  const refreshAll = async () => {
    await Promise.all([fetchDocuments(), fetchStats()]);
  };

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    try {
      const document = await api.knowledge.upload(file, uploadTitle);
      if (document.status === "indexed") {
        success("Document indexed", `${document.chunk_count} chunk(s) embedded from ${document.title}.`);
      } else if (document.status === "failed") {
        toastError("Indexing failed", document.error_message || "The document could not be indexed.");
      } else {
        success("Ingestion queued", "The background worker is processing this document.");
      }
      setUploadTitle("");
      setPage(1);
      await refreshAll();
    } catch (err: any) {
      toastError("Upload failed", err?.message || "The file could not be uploaded.");
    } finally {
      setUploading(false);
    }
  };

  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textTitle.trim() || textContent.trim().length < 20) return;
    setSavingText(true);
    try {
      const document = await api.knowledge.createText({
        title: textTitle.trim(),
        content: textContent,
      });
      if (document.status === "failed") {
        toastError("Indexing failed", document.error_message || "The text could not be indexed.");
      } else {
        success("Knowledge added", `${document.chunk_count} chunk(s) indexed.`);
      }
      setTextTitle("");
      setTextContent("");
      setShowTextForm(false);
      setPage(1);
      await refreshAll();
    } catch (err: any) {
      toastError("Could not save knowledge", err?.message || "Please check the text and retry.");
    } finally {
      setSavingText(false);
    }
  };

  const handleReindex = async (id: string) => {
    setBusyId(id);
    try {
      const document = await api.knowledge.reindex(id);
      if (document.status === "failed") {
        toastError("Reindex failed", document.error_message || "The document could not be indexed.");
      } else {
        success("Reindexed", `${document.title} has ${document.chunk_count} fresh chunk(s).`);
      }
      await refreshAll();
    } catch (err: any) {
      toastError("Reindex failed", err?.message || "Please try again.");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (id: string) => {
    setBusyId(id);
    try {
      await api.knowledge.remove(id);
      success("Document deleted", "Its chunks are removed from retrieval immediately.");
      setConfirmDeleteId(null);
      await refreshAll();
    } catch (err: any) {
      toastError("Delete failed", err?.message || "Please try again.");
    } finally {
      setBusyId(null);
    }
  };

  const handlePreview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (previewQuery.trim().length < 2) return;
    setPreviewing(true);
    try {
      const result = await api.knowledge.search({ query: previewQuery.trim(), top_k: 5 });
      setPreview(result);
      if (result.results.length === 0) {
        success("No grounded evidence", "No chunk cleared the similarity threshold for this query.");
      }
    } catch (err: any) {
      toastError("Retrieval preview failed", err?.message || "Please try again.");
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            <span>Retrieval-Augmented Generation</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Knowledge Base</h1>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Documents are chunked, embedded and indexed per workspace. Answers cite these sources, and
            nothing outside this workspace can be retrieved.
          </p>
        </div>

        {isAdmin ? (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowTextForm((open) => !open)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Paste text</span>
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-indigo-600/20 disabled:opacity-50"
            >
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              <span>{uploading ? "Indexing..." : "Upload document"}</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.markdown,.pdf"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) handleFileUpload(file);
              }}
            />
          </div>
        ) : (
          <div className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-[11px] text-slate-400">
            Read-only: only admins can upload, reindex or delete documents.
          </div>
        )}
      </div>

      {isAdmin && (
        <div className="glass-card rounded-2xl border border-slate-800 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[220px]">
            <label className="block text-[11px] font-medium text-slate-400 mb-1">
              Optional title (defaults to the file name)
            </label>
            <input
              value={uploadTitle}
              onChange={(event) => setUploadTitle(event.target.value)}
              placeholder="e.g. Refund & billing policy"
              maxLength={255}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600"
            />
          </div>
          <p className="text-[11px] text-slate-500 flex items-center gap-1.5 pb-2">
            <FileText className="w-3.5 h-3.5" />
            <span>.txt, .md or .pdf · up to 5 MB</span>
          </p>
        </div>
      )}

      {/* Paste text form */}
      {isAdmin && showTextForm && (
        <form onSubmit={handleTextSubmit} className="glass-card rounded-2xl border border-slate-700 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">Add knowledge from text</h2>
            <button
              type="button"
              onClick={() => setShowTextForm(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              aria-label="Close text form"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <input
            value={textTitle}
            onChange={(event) => setTextTitle(event.target.value)}
            required
            minLength={2}
            maxLength={255}
            placeholder="Title, e.g. Warranty policy"
            className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600"
          />
          <textarea
            value={textContent}
            onChange={(event) => setTextContent(event.target.value)}
            required
            minLength={20}
            rows={7}
            placeholder="Paste the policy, FAQ or product documentation..."
            className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600"
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-500">{textContent.trim().length} characters</span>
            <button
              type="submit"
              disabled={savingText || textTitle.trim().length < 2 || textContent.trim().length < 20}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
            >
              {savingText && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Index text</span>
            </button>
          </div>
        </form>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label: "Indexed documents",
            value: stats ? `${stats.indexed_documents}/${stats.total_documents}` : "—",
            icon: FileText,
          },
          { label: "Vector chunks", value: stats ? stats.total_chunks : "—", icon: Database },
          {
            label: "Indexed characters",
            value: stats ? stats.total_characters.toLocaleString() : "—",
            icon: Gauge,
          },
          {
            label: "Embedding model",
            value: stats ? `${stats.embedding_provider} · ${stats.embedding_dimension}d` : "—",
            icon: BookOpen,
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="glass-card rounded-2xl border border-slate-800 p-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] uppercase tracking-wider text-slate-400">{card.label}</span>
                <Icon className="w-4 h-4 text-indigo-400" />
              </div>
              <p className="text-lg font-bold text-white mt-2 font-mono">{card.value}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Document list */}
        <div className="xl:col-span-2 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => {
                    setStatusFilter(tab.value);
                    setPage(1);
                  }}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-[11px] font-semibold border transition-colors",
                    statusFilter === tab.value
                      ? "bg-indigo-600 border-indigo-500 text-white"
                      : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white hover:border-slate-700"
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                setAppliedSearch(searchInput.trim());
                setPage(1);
              }}
              className="flex items-center gap-1.5"
            >
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                <input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="Filter documents..."
                  aria-label="Filter knowledge documents"
                  className="pl-8 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600 w-52"
                />
              </div>
              <button
                type="submit"
                className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 text-xs font-semibold hover:bg-slate-700"
              >
                Filter
              </button>
            </form>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </span>
              <button
                type="button"
                onClick={refreshAll}
                className="px-2.5 py-1 rounded-lg bg-rose-500/10 border border-rose-500/30 font-semibold"
              >
                Retry
              </button>
            </div>
          )}

          {loading ? (
            <div className="space-y-2">
              {[0, 1, 2].map((row) => (
                <div key={row} className="glass-card rounded-2xl border border-slate-800 p-4 animate-pulse">
                  <div className="h-3 bg-slate-800 rounded w-1/3" />
                  <div className="h-2.5 bg-slate-800/70 rounded w-2/3 mt-3" />
                </div>
              ))}
            </div>
          ) : documents.length === 0 ? (
            <div className="glass-card rounded-2xl border border-slate-800 p-10 text-center">
              <BookOpen className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-white">
                {appliedSearch || statusFilter ? "No matching documents" : "No knowledge yet"}
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                {appliedSearch || statusFilter
                  ? "Try a different filter or clear the search."
                  : isAdmin
                  ? "Upload a policy document or paste text to ground AI answers."
                  : "An admin has not added any knowledge documents yet."}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="glass-card rounded-2xl border border-slate-800 p-4 hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-white truncate">{doc.title}</h3>
                        <span
                          className={cn(
                            "text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border",
                            statusStyles(doc.status)
                          )}
                        >
                          {doc.status}
                        </span>
                        <span className="text-[10px] text-slate-500 uppercase">
                          {doc.source_type}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1 truncate">
                        {doc.filename || "Pasted text"} · {formatBytes(doc.size_bytes)} ·{" "}
                        {doc.char_count.toLocaleString()} chars · {doc.chunk_count} chunks ·{" "}
                        {doc.embedding_dimension ? `${doc.embedding_dimension}d` : "not embedded"}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-1">
                        {doc.uploaded_by_name ? `Added by ${doc.uploaded_by_name}` : "System document"} ·{" "}
                        {new Date(doc.updated_at).toLocaleString()}
                      </p>
                      {doc.status === "failed" && doc.error_message && (
                        <p className="text-[11px] text-rose-300 mt-2 flex items-start gap-1.5">
                          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                          <span>{doc.error_message}</span>
                        </p>
                      )}
                    </div>

                    {isAdmin && (
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <button
                          type="button"
                          onClick={() => handleReindex(doc.id)}
                          disabled={busyId === doc.id}
                          title="Reindex document"
                          aria-label={`Reindex ${doc.title}`}
                          className="p-2 rounded-lg bg-slate-800/70 border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700 disabled:opacity-50"
                        >
                          {busyId === doc.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <RefreshCw className="w-3.5 h-3.5" />
                          )}
                        </button>

                        {confirmDeleteId === doc.id ? (
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleDelete(doc.id)}
                              disabled={busyId === doc.id}
                              className="px-2.5 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-[10px] font-bold disabled:opacity-50"
                            >
                              Confirm
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteId(null)}
                              className="px-2.5 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-[10px] font-semibold"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(doc.id)}
                            title="Delete document"
                            aria-label={`Delete ${doc.title}`}
                            className="p-2 rounded-lg bg-slate-800/70 border border-slate-700 text-slate-300 hover:text-rose-400 hover:bg-rose-500/10"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-2 text-xs text-slate-400">
                  <span>
                    Page {page} of {totalPages} · {total} documents
                  </span>
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => setPage((current) => Math.max(1, current - 1))}
                      disabled={page <= 1}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-40"
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                      disabled={page >= totalPages}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-40"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Retrieval preview */}
        <div className="space-y-3">
          <div className="glass-card rounded-2xl border border-slate-800 p-4">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Search className="w-4 h-4 text-indigo-400" />
              Retrieval preview
            </h2>
            <p className="text-[11px] text-slate-400 mt-1">
              See exactly which chunks ground an answer before a customer asks.
            </p>
            <form onSubmit={handlePreview} className="mt-3 space-y-2">
              <input
                value={previewQuery}
                onChange={(event) => setPreviewQuery(event.target.value)}
                placeholder="e.g. How long do refunds take?"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600"
              />
              <button
                type="submit"
                disabled={previewing || previewQuery.trim().length < 2}
                className="w-full px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {previewing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                <span>Run retrieval</span>
              </button>
            </form>

            {preview && (
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                  <span>
                    {preview.results.length} hit(s) · threshold {preview.threshold}
                  </span>
                  <span>{preview.took_ms} ms</span>
                </div>
                {preview.results.length === 0 ? (
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-[11px] text-slate-400">
                    No chunk cleared the threshold — chat would escalate this question to a human.
                  </div>
                ) : (
                  preview.results.map((hit) => (
                    <div key={hit.chunk_id} className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-white truncate">
                          {hit.document_title}
                        </span>
                        <span className="text-[10px] font-mono text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 rounded px-1.5 py-0.5">
                          {hit.score.toFixed(3)}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500">chunk #{hit.chunk_index}</p>
                      <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-4">{hit.excerpt}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <div className="glass-card rounded-2xl border border-slate-800 p-4 space-y-2">
            <h3 className="text-xs font-semibold text-white flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Grounding guarantees
            </h3>
            {[
              "Every vector query carries the workspace id.",
              "Chat cites sources or escalates — it never guesses.",
              "Deleting a document removes its chunks from retrieval.",
            ].map((line) => (
              <p key={line} className="text-[11px] text-slate-400 flex items-start gap-1.5">
                <span className="w-1 h-1 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0" />
                <span>{line}</span>
              </p>
            ))}
            {stats && (
              <p className="text-[10px] text-slate-500 font-mono pt-2 border-t border-slate-800">
                {stats.retrieval_scan_limit} candidates/query · {stats.similarity_threshold} cutoff
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
