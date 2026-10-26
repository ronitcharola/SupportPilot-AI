// Utility component for consistent glass card styling across the application
"use client";

export const glassCardVariants = {
  kpi: "hover:border-indigo-500/30 transition-all duration-200",
  panel: "hover:border-slate-700 transition-all duration-200",
  interactive: "cursor-pointer hover:border-indigo-500/40 hover:shadow-lg hover:shadow-indigo-500/5 transition-all duration-200",
} as const;
