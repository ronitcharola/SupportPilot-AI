"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import {
  ShieldCheck,
  LayoutDashboard,
  Inbox,
  ShieldAlert,
  BookOpen,
  BarChart3,
  Users,
  FileText,
  LogOut,
  ChevronDown,
  Building,
  Check,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, activeWorkspace, memberships, switchWorkspace, logout, isLoading } = useAuth();
  const [isWsDropdownOpen, setIsWsDropdownOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Loading workspace session...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    router.replace("/login");
    return null;
  }

  const navItems = [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "Ticket Inbox", href: "/tickets", icon: Inbox },
    { label: "AI Approvals", href: "/approvals", icon: ShieldAlert, badge: "HITL" },
    { label: "Knowledge Base", href: "/knowledge", icon: BookOpen, badge: "RAG" },
    { label: "Analytics", href: "/analytics", icon: BarChart3 },
    { label: "Team & Settings", href: "/settings/team", icon: Users },
    { label: "Audit Logs", href: "/audit", icon: FileText },
  ];

  const isAdmin = activeWorkspace?.role === "admin";

  return (
    <div className="min-h-screen flex bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800/80 bg-slate-900/50 backdrop-blur-xl flex flex-col justify-between p-4 flex-shrink-0">
        <div>
          {/* Brand */}
          <div className="flex items-center gap-2.5 px-2 py-3 mb-4">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center shadow-glow">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-sm tracking-tight text-white block">SupportPilot AI</span>
              <span className="text-[10px] text-slate-400 font-mono">Enterprise v1.0</span>
            </div>
          </div>

          {/* Workspace Switcher */}
          <div className="relative mb-6">
            <button
              type="button"
              onClick={() => setIsWsDropdownOpen(!isWsDropdownOpen)}
              className="w-full flex items-center justify-between p-2.5 rounded-xl bg-slate-800/50 hover:bg-slate-800 border border-slate-700/60 text-left transition-all"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-indigo-950 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
                  <Building className="w-3.5 h-3.5 text-indigo-400" />
                </div>
                <div className="truncate">
                  <span className="text-xs font-semibold text-white block truncate">
                    {activeWorkspace?.workspace_name || "Select Workspace"}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono block">
                    /{activeWorkspace?.workspace_slug}
                  </span>
                </div>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            </button>

            {isWsDropdownOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 py-1 rounded-xl bg-slate-900 border border-slate-700 shadow-2xl z-50">
                <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                  Your Workspaces
                </div>
                {memberships.map((m) => (
                  <button
                    key={m.workspace_id}
                    onClick={() => {
                      switchWorkspace(m.workspace_id);
                      setIsWsDropdownOpen(false);
                    }}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 text-xs text-left transition-colors",
                      m.workspace_id === activeWorkspace?.workspace_id
                        ? "bg-indigo-600/20 text-indigo-300 font-medium"
                        : "text-slate-300 hover:bg-slate-800"
                    )}
                  >
                    <span className="truncate">{m.workspace_name}</span>
                    {m.workspace_id === activeWorkspace?.workspace_id && (
                      <Check className="w-3.5 h-3.5 text-indigo-400" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Navigation Items */}
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all group",
                    isActive
                      ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={cn("w-4 h-4", isActive ? "text-white" : "text-slate-400 group-hover:text-indigo-400")} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span
                      className={cn(
                        "text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded-full border",
                        isActive
                          ? "bg-white/20 text-white border-white/20"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* User Card & Logout */}
        <div className="pt-4 border-t border-slate-800/80">
          <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-slate-800 mb-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 font-bold text-xs flex items-center justify-center flex-shrink-0">
                {user.full_name.charAt(0).toUpperCase()}
              </div>
              <div className="truncate">
                <span className="text-xs font-medium text-white block truncate">{user.full_name}</span>
                <span
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-wider block",
                    isAdmin ? "text-indigo-400" : "text-cyan-400"
                  )}
                >
                  {isAdmin ? "Admin" : "Support Agent"}
                </span>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-14 border-b border-slate-800/80 bg-slate-900/40 backdrop-blur-md px-6 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Workspace:</span>
            <span className="font-semibold text-white bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
              {activeWorkspace?.workspace_name}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs bg-indigo-950/40 border border-indigo-500/30 text-indigo-300 px-2.5 py-1 rounded-full">
              <Cpu className="w-3.5 h-3.5 text-indigo-400" />
              <span>AI Provider: Mock (Demo Active)</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Multi-Tenant Guard: Enforced</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
