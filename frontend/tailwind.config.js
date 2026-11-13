/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: { bg: v("bg"), card: v("card"), soft: v("soft"), line: v("line"), ink: v("ink"), mute: v("mute"), brand: v("brand"), xp: v("xp") },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        display: ['"Sora"', '"Plus Jakarta Sans"', "system-ui", "sans-serif"],
      },
      boxShadow: { card: "0 1px 2px rgb(16 18 40 / 0.04), 0 8px 24px -12px rgb(16 18 40 / 0.12)" },
      keyframes: {
        pop: { "0%": { transform: "scale(.92)", opacity: 0 }, "100%": { transform: "scale(1)", opacity: 1 } },
        rise: { "0%": { transform: "translateY(8px)", opacity: 0 }, "100%": { transform: "translateY(0)", opacity: 1 } },
        floatup: { "0%": { transform: "translateY(0)", opacity: 1 }, "100%": { transform: "translateY(-36px)", opacity: 0 } },
        shake: { "0%,100%": { transform: "translateX(0)" }, "25%": { transform: "translateX(-5px)" }, "75%": { transform: "translateX(5px)" } },
        fall: { "0%": { transform: "translateY(-10vh) rotate(0)", opacity: 1 }, "100%": { transform: "translateY(105vh) rotate(540deg)", opacity: 0.6 } },
      },
      animation: { pop: "pop .25s ease-out", rise: "rise .35s ease-out both", floatup: "floatup 1.1s ease-out forwards", shake: "shake .3s ease-in-out", fall: "fall 2.6s linear forwards" },
    },
  },
  plugins: [],
};
