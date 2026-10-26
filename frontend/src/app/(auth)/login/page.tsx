"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import { ShieldCheck, Lock, Mail, ArrowRight, Sparkles, AlertCircle, Loader2 } from "lucide-react";

export default function LoginPage() {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ email, password });
    } catch (err: any) {
      setError(err.message || "Failed to authenticate. Please check your credentials.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (userEmail: string, userPass: string) => {
    setEmail(userEmail);
    setPassword(userPass);
    setError(null);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-slate-950">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-indigo-600/15 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[400px] h-[250px] bg-purple-600/10 blur-[100px] rounded-full pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-glow mb-4">
            <ShieldCheck className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">SupportPilot AI</h1>
          <p className="text-sm text-slate-400 mt-2">
            Multi-Tenant Customer Support SaaS with Human-in-the-Loop Safeguards
          </p>
        </div>

        {/* Login Card */}
        <div className="glass-card rounded-2xl p-8 shadow-2xl relative border border-slate-800">
          <h2 className="text-xl font-semibold text-white mb-2">Sign In to Workspace</h2>
          <p className="text-xs text-slate-400 mb-6">
            Enter your enterprise credentials to access your support dashboard.
          </p>

          {error && (
            <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="agent@company.com"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-sm placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-sm placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || isLoading}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white text-sm font-semibold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Verifying Session...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Logins */}
          <div className="mt-8 pt-6 border-t border-slate-800/80">
            <div className="flex items-center gap-1.5 text-xs font-medium text-indigo-400 mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              <span>One-Click Demo Credentials:</span>
            </div>
            <div className="grid grid-cols-1 gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill("admin@acme.com", "SupportPilot2026!")}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 text-xs transition-colors flex items-center justify-between"
              >
                <div>
                  <span className="text-white font-medium">Alice Admin</span>
                  <span className="text-slate-500 ml-1.5">(Admin · Acme Corp)</span>
                </div>
                <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  Full Access
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickFill("agent@acme.com", "SupportPilot2026!")}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 text-xs transition-colors flex items-center justify-between"
              >
                <div>
                  <span className="text-white font-medium">Bob Support</span>
                  <span className="text-slate-500 ml-1.5">(Agent · Acme Corp)</span>
                </div>
                <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  Support Agent
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickFill("admin@beta.com", "SupportPilot2026!")}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 text-xs transition-colors flex items-center justify-between"
              >
                <div>
                  <span className="text-white font-medium">Bella Beta</span>
                  <span className="text-slate-500 ml-1.5">(Admin · Beta Industries)</span>
                </div>
                <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  Tenant Isolation
                </span>
              </button>
            </div>
          </div>

          {/* Registration link */}
          <div className="mt-6 text-center text-xs text-slate-400">
            Need a new workspace?{" "}
            <Link href="/register" className="text-indigo-400 hover:text-indigo-300 font-medium">
              Create an account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
