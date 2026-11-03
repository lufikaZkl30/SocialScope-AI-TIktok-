/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['"Manrope Variable"', 'Segoe UI', 'system-ui', 'sans-serif'] },
      colors: {
        ink: { 950: '#070B16', 900: '#0B1120', 800: '#111A31', 700: '#192544', 600: '#26345E' },
        mist: { 100: '#E8ECF8', 300: '#B3BDDA', 500: '#8794BA' },
        cyan: { 400: '#22D3EE', 500: '#06B6D4' },
        violet: { 300: '#C4B5FD', 400: '#A78BFA', 500: '#8B5CF6' },
        neg: '#FB7185', warn: '#FBBF24',
      },
    },
  },
  plugins: [],
};
