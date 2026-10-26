"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ChatCitation } from "@/lib/api";
import { useToast } from "@/components/toast";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Bot,
  Loader2,
  Send,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[];
  grounded?: boolean;
  escalated?: boolean;
  reason?: string | null;
}

const STARTER_QUESTIONS = [
  "How long do refunds take?",
  "Do you offer a nonprofit discount?",
  "How do I set up SAML SSO with Okta?",
  "My package is delayed — what should I do?",
];

function ChatContent() {
  const searchParams = useSearchParams();
  const customerEmail = searchParams.get("email") || "customer@acme.com";
  const { error: toastError } = useToast();

  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, sending]);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (trimmed.length < 2 || sending) return;

    const userTurn: ChatTurn = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    setTurns((previous) => [...previous, userTurn]);
    setMessage("");
    setSending(true);

    try {
      const response = await api.ai.chat({
        message: trimmed,
        workspace_slug: "acme-corp",
        customer_email: customerEmail,
      });
      setTurns((previous) => [
        ...previous,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          grounded: response.grounded,
          escalated: response.escalated,
          reason: response.escalation_reason,
        },
      ]);
    } catch (err: any) {
      toastError("The assistant is unavailable", err?.message || "Please try again in a moment.");
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
          <Sparkles className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">Acme Corp AI Assistant</h1>
          <p className="text-xs text-slate-400 mt-1 max-w-lg mx-auto">
            Answers come only from Acme Corp&apos;s published knowledge base, with sources cited.
            If nothing matches, you are handed to a human agent.
          </p>
        </div>
        <div className="inline-flex items-center gap-1.5 text-[11px] text-slate-400 bg-slate-900 border border-slate-800 rounded-full px-3 py-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Workspace-isolated retrieval · human escalation on low evidence</span>
        </div>
      </div>

      {/* Conversation */}
      <div
        className="glass-card rounded-3xl border border-slate-800 p-5 min-h-[320px] space-y-4"
        aria-live="polite"
        aria-label="Support chat conversation"
      >
        {turns.length === 0 && !sending && (
          <div className="py-8 text-center space-y-4">
            <Bot className="w-10 h-10 text-slate-600 mx-auto" />
            <div>
              <p className="text-sm font-semibold text-white">Ask a question to get started</p>
              <p className="text-xs text-slate-400 mt-1">
                Try one of these, or type your own question below.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {STARTER_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => sendMessage(question)}
                  className="px-3 py-1.5 rounded-full bg-slate-900 border border-slate-700 text-[11px] text-slate-300 hover:text-white hover:border-indigo-500/50 transition-colors"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn) =>
          turn.role === "user" ? (
            <div key={turn.id} className="flex items-start justify-end gap-2.5">
              <div className="max-w-[82%] p-3.5 rounded-2xl bg-indigo-600 text-white text-xs leading-relaxed whitespace-pre-wrap">
                {turn.content}
              </div>
              <div className="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0">
                <User className="w-3.5 h-3.5 text-slate-300" />
              </div>
            </div>
          ) : (
            <div key={turn.id} className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center flex-shrink-0">
                <Bot className="w-3.5 h-3.5 text-indigo-300" />
              </div>
              <div className="max-w-[88%] space-y-2.5">
                <div
                  className={cn(
                    "p-3.5 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap border",
                    turn.escalated
                      ? "bg-amber-500/10 border-amber-500/30 text-amber-100"
                      : "bg-slate-900 border-slate-800 text-slate-200"
                  )}
                >
                  {turn.content}
                </div>

                {turn.escalated && (
                  <div className="rounded-2xl border border-amber-500/25 bg-amber-950/20 p-3.5 space-y-2">
                    <p className="text-[11px] text-amber-200/90 flex items-center gap-1.5">
                      <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                      <span>{turn.reason || "This question needs a human support agent."}</span>
                    </p>
                    <Link
                      href={`/portal?email=${encodeURIComponent(customerEmail)}`}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px] font-bold"
                    >
                      <span>Submit a support request</span>
                      <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>
                )}

                {!!turn.citations?.length && (
                  <div className="space-y-1.5">
                    <p className="text-[10px] uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                      <BookOpen className="w-3 h-3" />
                      Sources
                    </p>
                    {turn.citations.map((citation) => (
                      <div
                        key={`${turn.id}-${citation.number}-${citation.chunk_index}`}
                        className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 space-y-1"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-semibold text-indigo-300">
                            [{citation.number}] {citation.document_title}
                          </span>
                          <span className="text-[9px] font-mono text-slate-500">
                            {(citation.score * 100).toFixed(0)}% match
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-3">
                          {citation.excerpt}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )
        )}

        {sending && (
          <div className="flex items-center gap-2.5 text-slate-400">
            <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-indigo-300" />
            </div>
            <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-2xl bg-slate-900 border border-slate-800">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
              <span className="text-[11px]">Searching the knowledge base...</span>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Composer */}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          sendMessage(message);
        }}
        className="glass-card rounded-2xl border border-slate-800 p-4 space-y-3"
      >
        <label htmlFor="chat-message" className="text-[11px] font-medium text-slate-400">
          Your question
        </label>
        <textarea
          id="chat-message"
          ref={inputRef}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              sendMessage(message);
            }
          }}
          rows={2}
          maxLength={4000}
          placeholder="Ask about refunds, shipping, SSO, billing..."
          className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600 resize-none"
        />
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-500">
            AI answers are advisory. Refunds and account changes always need human approval.
          </span>
          <button
            type="submit"
            disabled={sending || message.trim().length < 2}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 shadow-md shadow-indigo-600/20 disabled:opacity-50"
          >
            {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            <span>Ask</span>
          </button>
        </div>
      </form>

      <div className="flex items-center justify-between text-xs">
        <Link href={`/portal?email=${encodeURIComponent(customerEmail)}`} className="text-indigo-400 hover:text-indigo-300 font-medium">
          ← My support requests
        </Link>
        <span className="text-slate-500">Signed in as {customerEmail}</span>
      </div>
    </div>
  );
}

export default function CustomerChatPage() {
  return (
    <Suspense
      fallback={
        <div className="py-24 flex justify-center items-center text-slate-400 gap-2">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
          <span className="text-xs">Loading the assistant...</span>
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
