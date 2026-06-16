/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#2563eb", dark: "#1d4ed8" },
        ok: "#16a34a",
        warn: "#f59e0b",
        error: "#dc2626",
        bg: "#0f172a",
        "bg-soft": "#111827",
      },
    },
  },
  plugins: [],
};
