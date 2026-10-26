"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { api, TeamMember } from "@/lib/api";
import { Users, UserPlus, Shield, ShieldCheck, Mail, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

export default function TeamSettingsPage() {
  const { activeWorkspace } = useAuth();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<"support_agent" | "admin">("support_agent");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isAdmin = activeWorkspace?.role === "admin";

  const fetchMembers = async () => {
    try {
      setLoading(true);
      const data = await api.workspaces.getMembers();
      setMembers(data);
    } catch (err: any) {
      setError(err.message || "Failed to load team members");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMembers();
  }, [activeWorkspace?.workspace_id]);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);
    try {
      await api.workspaces.addMember({
        email,
        full_name: fullName,
        role,
      });
      setSuccess(`Successfully added ${email} as ${role.replace("_", " ")}.`);
      setEmail("");
      setFullName("");
      await fetchMembers();
    } catch (err: any) {
      setError(err.message || "Failed to add member");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <Users className="w-6 h-6 text-indigo-400" />
          <span>Team & Workspace Members</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Manage member permissions, assignments, and access control for <span className="text-white font-medium">{activeWorkspace?.workspace_name}</span>.
        </p>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* Grid: Form (Admin only) & Member List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Add Member Card */}
        <div className="glass-card rounded-2xl p-6 border border-slate-800 lg:col-span-1 h-fit">
          <div className="flex items-center gap-2 text-white font-semibold text-sm mb-2">
            <UserPlus className="w-4 h-4 text-indigo-400" />
            <span>Add Team Member</span>
          </div>
          <p className="text-xs text-slate-400 mb-5">
            Grant workspace access to a colleague.
          </p>

          {!isAdmin ? (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start gap-2.5">
              <Shield className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block mb-0.5">Admin Role Required</span>
                <span>Your current role is Support Agent. Only Workspace Admins can add or modify team members.</span>
              </div>
            </div>
          ) : (
            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="colleague@acme.com"
                    className="w-full pl-10 pr-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Dave Developer"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Assigned Role</label>
                <select
                  value={role}
                  onChange={(e: any) => setRole(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                >
                  <option value="support_agent">Support Agent (Review, Approve, Reply)</option>
                  <option value="admin">Admin (Full Control, Settings, Members)</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Adding Member...</span>
                  </>
                ) : (
                  <span>Add Member</span>
                )}
              </button>
            </form>
          )}
        </div>

        {/* Member List Table */}
        <div className="glass-card rounded-2xl p-6 border border-slate-800 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white">Current Members ({members.length})</h2>
            <span className="text-[10px] text-slate-400 font-mono">Workspace ID: {activeWorkspace?.workspace_id}</span>
          </div>

          {loading ? (
            <div className="py-12 flex justify-center items-center gap-2 text-xs text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              <span>Fetching team members...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-medium">
                    <th className="pb-3 px-3">Member</th>
                    <th className="pb-3 px-3">Email</th>
                    <th className="pb-3 px-3">Role</th>
                    <th className="pb-3 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {members.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-3 px-3 font-medium text-white flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 font-bold flex items-center justify-center flex-shrink-0">
                          {m.full_name ? m.full_name.charAt(0).toUpperCase() : "U"}
                        </div>
                        <span>{m.full_name || "Unnamed"}</span>
                      </td>
                      <td className="py-3 px-3 text-slate-300 font-mono text-[11px]">{m.email}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${
                            m.role === "admin"
                              ? "bg-indigo-500/10 text-indigo-300 border-indigo-500/30"
                              : "bg-cyan-500/10 text-cyan-300 border-cyan-500/30"
                          }`}
                        >
                          <ShieldCheck className="w-3 h-3" />
                          <span>{m.role.replace("_", " ")}</span>
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px]">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          <span>Active</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
