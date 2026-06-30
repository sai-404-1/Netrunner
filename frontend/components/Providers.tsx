"use client";

import { AuthProvider } from "@/components/AuthProvider";
import ClientLayout from "@/components/ClientLayout";
import { ToastProvider } from "@/components/Toast";
import { ThemeProvider } from "@/components/ThemeProvider";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <ClientLayout>{children}</ClientLayout>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
