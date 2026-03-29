/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        background: '#f8fafc',
        surface: '#ffffff',
        border: '#e2e8f0',
        'text-primary': '#0f172a',
        'text-secondary': '#64748b',
        'accent-indigo': '#6366f1',
        'accent-violet': '#7c3aed',
        'accent-green': '#10b981',
        'accent-red': '#ef4444',
        'accent-yellow': '#f59e0b',
        'accent-cyan': '#06b6d4',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
