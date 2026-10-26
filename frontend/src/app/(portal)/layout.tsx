import React from "react";
import Link from "next/link";
import { ShieldCheck, ArrowLeft, Headphones, Sparkles, LifeBuoy } from "lucide-react";

export default function CustomerPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-indigo-500/30">
      {/* Header */}
      <header className="h-16 border-b border-slate-800 bg-slate-900/60 backdrop-blur-xl px-6 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center shadow-glow">
            <Headphones className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="font-bold text-sm tracking-tight text-white block">Acme Corp Support Portal</span>
            <span className="text-[10px] text-slate-400">Customer Self-Service Hub</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/portal"
            className="px-3 py-1.5 rounded-xl text-slate-300 hover:text-white hover:bg-slate-800 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <LifeBuoy className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">My Requests</span>
          </Link>
          <Link
            href="/portal/chat"
            className="px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Ask AI</span>
          </Link>
          <Link
            href="/dashboard"
            className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Agent Dashboard</span>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 max-w-5xl mx-auto w-full">{children}</main>

      {/* Footer */}
      <footer className="py-6 border-t border-slate-900 text-center text-xs text-slate-500">
        Powered by SupportPilot AI Enterprise Support Engine
      </footer>
    </div>
  );
}
