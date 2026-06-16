/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f4f4f5',
          100: '#e4e4e7',
          500: '#ffffff',
          600: '#d4d4d8',
          900: '#18181b',
        },
        darkbg: '#000000',
        darkcard: '#09090b',
        neonpurple: '#71717a',
        neongreen: '#e4e4e7',
      },
    },
  },
  plugins: [],
}
