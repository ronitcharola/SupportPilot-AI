"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { ShieldCheck, Loader2 } from "lucide-react";

export default function HomePage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      if (user) {
        router.replace("/dashboard");
      } else {
        router.replace("/login");
      }
    }
  }, [user, isLoading, router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-gradient-to-br from-slate-950 via-indigo-950/20 to-slate-950">
      <div className="flex items-center gap-3 text-indigo-400 mb-4 animate-pulse">
        <ShieldCheck className="w-10 h-10" />
        <span className="text-2xl font-bold tracking-tight text-white">SupportPilot AI</span>
      </div>
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />
        <span>Initializing enterprise workspace context...</span>
      </div>
    </div>
  );
}
