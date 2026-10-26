/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        glow: '0 0 0 1px rgba(34, 211, 238, 0.25), 0 25px 60px rgba(15, 23, 42, 0.7)',
      },
    },
  },
  plugins: [],
};
