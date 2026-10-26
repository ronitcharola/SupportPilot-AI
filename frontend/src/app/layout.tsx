import type { Metadata } from "next";
import { AuthProvider } from "@/contexts/auth-context";
import { ToastProvider } from "@/components/toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "SupportPilot AI — Enterprise AI Support with Human Approval",
  description: "Multi-tenant AI customer support SaaS platform with Human-in-the-Loop approval safeguards.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased selection:bg-indigo-500/30">
        <ToastProvider>
          <AuthProvider>{children}</AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
