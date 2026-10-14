import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CHRONOS-ZERO // Speculative Execution & Formal Verification Kernel",
  description:
    "Low-Latency Z3 SMT Formal Proofs & Postgres Copy-on-Write Speculative Execution Kernel for High-Stakes Autonomous AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-surface-container-lowest font-body-md text-body-md text-on-surface antialiased min-h-screen selection:bg-primary-container selection:text-on-primary-container overflow-hidden">
        {/* Ambient Focal Glow Orbs */}
        <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_80%_60%_at_50%_-15%,rgba(78,222,163,0.08),rgba(15,19,28,0))] z-0" />
        <div className="fixed inset-0 pointer-events-none bg-[linear-gradient(to_right,rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:32px_32px] opacity-40 z-0" />
        <div className="relative z-10 h-screen w-screen flex flex-col">
          {children}
        </div>
      </body>
    </html>
  );
}
