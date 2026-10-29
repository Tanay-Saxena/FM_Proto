"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5_000 } } }));
  return (
    <QueryClientProvider client={qc}>
      {children}
      <Toaster position="bottom-center" offset={{ bottom: 150, left: 16, right: 16 }} mobileOffset={{ bottom: 150, left: 16, right: 16 }} gap={8} toastOptions={{ duration: 2200, style: { fontFamily: "var(--font-body)", background: "#0e1a13", color: "#fff", border: "0", borderRadius: "999px", fontWeight: 600, boxShadow: "0 16px 40px -12px rgba(0,0,0,.5)" } }} />
    </QueryClientProvider>
  );
}
