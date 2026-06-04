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
          DEFAULT: "#211D17", // primary text — warm near-black (darkened)
          soft: "#3F3A32", // secondary text (darkened for readability)
        },
        muted: "#615A4E", // tertiary / labels (darkened from #8C857A)
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
