/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        'bank-bg': '#0B1110', 
        'bank-panel': '#16201c', 
        'bank-border': '#1F2E2A',
        'brand': {
          DEFAULT: '#52FFB8',
          dark: '#00C978',
          glow: 'rgba(82, 255, 184, 0.15)',
        }
      },
    },
  },
  plugins: [],
}