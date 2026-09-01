/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0d1117",
        surface: "#161b22",
        "surface-light": "#21262d",
        brand: {
          cyan: "#00e5ff",
          amber: "#ff9100",
          yellow: "#ffea00",
          green: "#00e676",
        },
      },
    },
  },
  plugins: [],
};
