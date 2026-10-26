"use client";

import React, { createContext, useCallback, useContext, useState } from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "info";

interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastItem extends ToastOptions {
  id: string;
}

interface ToastContextValue {
  toast: (options: ToastOptions) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: "border-emerald-500/40 bg-emerald-950/80 text-emerald-100",
  error: "border-rose-500/40 bg-rose-950/80 text-rose-100",
  info: "border-indigo-500/40 bg-indigo-950/80 text-indigo-100",
};

const VARIANT_ICONS: Record<ToastVariant, React.ElementType> = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((previous) => previous.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback(
    ({ title, description, variant = "info" }: ToastOptions) => {
      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setToasts((previous) => [...previous, { id, title, description, variant }]);
      window.setTimeout(() => dismiss(id), 5000);
    },
    [dismiss]
  );

  const success = useCallback(
    (title: string, description?: string) => toast({ title, description, variant: "success" }),
    [toast]
  );

  const error = useCallback(
    (title: string, description?: string) => toast({ title, description, variant: "error" }),
    [toast]
  );

  return (
    <ToastContext.Provider value={{ toast, success, error }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2 px-4 sm:px-0"
      >
        {toasts.map((item) => {
          const Icon = VARIANT_ICONS[item.variant || "info"];
          return (
            <div
              key={item.id}
              role="status"
              className={cn(
                "flex items-start gap-3 rounded-xl border p-3 shadow-2xl backdrop-blur-md",
                VARIANT_STYLES[item.variant || "info"]
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold">{item.title}</p>
                {item.description && (
                  <p className="mt-0.5 text-[11px] opacity-80 break-words">{item.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                aria-label="Dismiss notification"
                className="rounded-md p-0.5 opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-white/40"
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
