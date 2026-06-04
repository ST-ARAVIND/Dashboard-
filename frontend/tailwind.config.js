/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Trading-desk palette.
        bg: { DEFAULT: "#0a0e14", panel: "#111722", soft: "#161e2e" },
        line: "#1f2937",
        bull: "#16c784",
        bear: "#ea3943",
        accent: "#3b82f6",
        muted: "#64748b",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
