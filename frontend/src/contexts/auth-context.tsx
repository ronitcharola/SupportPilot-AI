"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, User, WorkspaceMemberSummary, AuthResponse } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  activeWorkspace: WorkspaceMemberSummary | null;
  memberships: WorkspaceMemberSummary[];
  csrfToken: string;
  isLoading: boolean;
  login: (credentials: { email: string; password: string }) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; workspace_name: string }) => Promise<void>;
  logout: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => void;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceMemberSummary | null>(null);
  const [memberships, setMemberships] = useState<WorkspaceMemberSummary[]>([]);
  const [csrfToken, setCsrfToken] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  const handleAuthPayload = (data: AuthResponse) => {
    setUser(data.user);
    setMemberships(data.memberships);
    setCsrfToken(data.csrf_token);

    // Pick active workspace: preferred stored id, or server active, or first
    const savedWsId = api.getActiveWorkspace();
    const resolved =
      data.memberships.find((m) => m.workspace_id === savedWsId) ||
      data.active_workspace ||
      (data.memberships.length > 0 ? data.memberships[0] : null);

    setActiveWorkspace(resolved);
    if (resolved) {
      api.setActiveWorkspace(resolved.workspace_id);
    }
  };

  const refreshSession = async () => {
    try {
      setIsLoading(true);
      const data = await api.auth.me();
      handleAuthPayload(data);
    } catch {
      setUser(null);
      setActiveWorkspace(null);
      setMemberships([]);
      api.setActiveWorkspace(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshSession();
  }, []);

  const login = async (credentials: { email: string; password: string }) => {
    setIsLoading(true);
    try {
      const data = await api.auth.login(credentials);
      handleAuthPayload(data);
      router.push("/dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: { email: string; password: string; full_name: string; workspace_name: string }) => {
    setIsLoading(true);
    try {
      const resp = await api.auth.register(data);
      handleAuthPayload(resp);
      router.push("/dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } catch {
      // Continue cleanup
    } finally {
      setUser(null);
      setActiveWorkspace(null);
      setMemberships([]);
      api.setActiveWorkspace(null);
      router.push("/login");
    }
  };

  const switchWorkspace = (workspaceId: string) => {
    const target = memberships.find((m) => m.workspace_id === workspaceId);
    if (target) {
      setActiveWorkspace(target);
      api.setActiveWorkspace(target.workspace_id);
      // Reload current route data
      window.location.reload();
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        activeWorkspace,
        memberships,
        csrfToken,
        isLoading,
        login,
        register,
        logout,
        switchWorkspace,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
