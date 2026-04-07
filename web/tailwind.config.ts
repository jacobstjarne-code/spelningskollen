import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#0C0B0F", surface: "#16141C", elevated: "#1E1B26", stage: "#221E2D" },
        accent: { DEFAULT: "#D43C7E", bright: "#F04E96", dim: "#A82D63" },
        warm: { DEFAULT: "#D4A04A", dim: "#B8872E" },
        txt: { primary: "#F0ECF4", secondary: "#9B95A8", muted: "#6B6578" },
      },
      fontFamily: {
        display: ["Georgia", "Times New Roman", "serif"],
        body: ["system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      borderRadius: {
        card: "10px",
        sm: "6px",
      },
    },
  },
  plugins: [],
};
export default config;
