/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        orange: {
          450: '#ff7a1a',
        },
      },
    },
  },
  plugins: [],
}
