/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0f',
        surface: 'rgba(255,255,255,0.05)',
        'accent-violet': '#7c3aed',
        'accent-cyan': '#06b6d4',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      backdropBlur: {
        glass: '20px',
      }
    },
  },
  plugins: [],
}
