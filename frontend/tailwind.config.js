/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        'bank-bg': '#0d1117',
        'bank-card': '#161b22',
        'bank-surface': '#1c2333',
        'bank-border': '#30363d',
      },
    },
  },
  plugins: [],
};
