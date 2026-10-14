import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CHRONOS-ZERO // Mission Control",
  description:
    "Speculative Execution & Formal Verification Kernel for Autonomous AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="h-screen w-screen overflow-hidden bg-[#090D16] text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
