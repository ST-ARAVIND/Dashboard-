/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Warm "sandstone" light palette (Claude-like).
        bg: {
          DEFAULT: "#F4EFE6", // page background — warm sand
          panel: "#FCFBF8", // cards — near-white warm
          soft: "#EDE7DA", // hover / secondary surfaces
        },
        line: "#E3DBCB", // borders / dividers
        ink: {
          DEFAULT: "#2A2620", // primary text — warm near-black
          soft: "#5C564C", // secondary text
        },
        muted: "#8C857A", // tertiary / labels
        bull: "#15803D", // gains (tuned for light bg)
        bear: "#C0392B", // losses
        accent: "#BE5A3A", // terracotta — links / active / highlights
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
