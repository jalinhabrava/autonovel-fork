/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        txf: {
          bg: 'var(--txf-color-bg)',
          frame: 'var(--txf-color-frame)',
          sidebar: 'var(--txf-color-sidebar)',
          canvas: 'var(--txf-color-canvas)',
          surface: 'var(--txf-color-surface)',
          'surface-muted': 'var(--txf-color-surface-muted)',
          'surface-soft': 'var(--txf-color-surface-soft)',
          border: 'var(--txf-color-border)',
          'border-strong': 'var(--txf-color-border-strong)',
          text: 'var(--txf-color-text)',
          muted: 'var(--txf-color-text-muted)',
          subtle: 'var(--txf-color-text-subtle)',
          accent: 'var(--txf-color-accent)',
          'accent-hover': 'var(--txf-color-accent-hover)',
          'accent-soft': 'var(--txf-color-accent-soft)',
          action: 'var(--txf-color-action)',
          'action-hover': 'var(--txf-color-action-hover)',
          'action-soft': 'var(--txf-color-action-soft)',
          'nav-active': 'var(--txf-color-nav-active)',
          'nav-active-text': 'var(--txf-color-nav-active-text)',
          focus: 'var(--txf-color-focus-ring)',
          danger: 'var(--txf-color-danger)',
          'danger-soft': 'var(--txf-color-danger-soft)',
          success: 'var(--txf-color-success)',
          'success-soft': 'var(--txf-color-success-soft)',
          warning: 'var(--txf-color-warning)',
          'warning-soft': 'var(--txf-color-warning-soft)',
        },
      },
      boxShadow: {
        'txf-card': 'var(--txf-shadow-card)',
        'txf-panel': 'var(--txf-shadow-panel)',
        'txf-floating': 'var(--txf-shadow-floating)',
      },
      borderRadius: {
        'txf-card': 'var(--txf-radius-card)',
        'txf-button': 'var(--txf-radius-button)',
      },
    },
  },
  plugins: [],
};
