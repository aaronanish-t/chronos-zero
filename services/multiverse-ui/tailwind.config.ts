import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/hooks/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#090D16",
        surface: {
          DEFAULT: "#0F172A",
          muted: "#131E33",
          hover: "#1E293B",
        },
        border: {
          DEFAULT: "#1E293B",
          subtle: "#334155",
          highlight: "#475569",
        },
        chronos: {
          crimson: "#EF4444",
          emerald: "#10B981",
          amber: "#F59E0B",
          cyan: "#06B6D4",
          violet: "#8B5CF6",
          dark: "#090D16",
          border: "#1E293B",
        },
      },
      fontFamily: {
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "SF Mono",
          "Cascadia Code",
          "Consolas",
          "monospace",
        ],
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      animation: {
        "pulse-fast": "pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "flash-danger": "flashDanger 0.8s ease-in-out infinite alternate",
        "stream-flow": "streamFlow 2s linear infinite",
      },
      keyframes: {
        flashDanger: {
          "0%": { backgroundColor: "rgba(239, 68, 68, 0.15)", borderColor: "#EF4444" },
          "100%": { backgroundColor: "rgba(239, 68, 68, 0.35)", borderColor: "#DC2626" },
        },
        streamFlow: {
          "0%": { strokeDashoffset: "24" },
          "100%": { strokeDashoffset: "0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
