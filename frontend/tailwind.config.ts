import type { Config } from 'tailwindcss';
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './hooks/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}', './store/**/*.{ts,tsx}'],
  theme: { extend: { colors: { ey: { yellow: '#FFE600', black: '#111111', ink: '#1C1C1C', muted: '#6B7280', border: '#E5E7EB', surface: '#FAFAFA', surface2: '#F4F4F5' } }, boxShadow: { soft: '0 8px 24px rgba(17,17,17,0.06)' }, borderRadius: { xl2: '1.25rem' } } },
  plugins: [],
};
export default config;