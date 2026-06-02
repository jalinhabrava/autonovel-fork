import React from 'react';

export function StatusChip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-txf-border bg-txf-surface-soft px-3 py-1 text-txf-muted">{children}</span>;
}

export function Button({ children, variant = 'primary', disabled = false, onClick, ...rest }: { children: React.ReactNode; variant?: 'primary' | 'secondary'; disabled?: boolean; onClick?: () => void } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" disabled={disabled} onClick={onClick} className={`rounded-2xl px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${variant === 'primary' ? 'bg-txf-action text-txf-nav-active-text hover:bg-txf-action-hover' : 'bg-txf-surface text-txf-text border border-txf-border-strong hover:bg-txf-surface-soft'}`} {...rest}>{children}</button>;
}

export function Metric({ label, value, note }: { label: string; value: React.ReactNode; note: string }) {
  return <div className="rounded-txf-card border border-txf-border bg-txf-surface p-5 shadow-txf-card"><div className="text-xs uppercase tracking-wide text-txf-subtle">{label}</div><div className="mt-2 text-3xl font-semibold tracking-tight">{value}</div><p className="mt-2 text-sm text-txf-subtle">{note}</p></div>;
}

export function TopBar({ title, subtitle, actions }: { title: string; subtitle: string; actions?: React.ReactNode }) {
  return <div className="flex flex-col gap-3 border-b border-txf-border bg-txf-canvas p-5 lg:flex-row lg:items-center lg:justify-between"><div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 text-sm text-txf-subtle">{subtitle}</p></div><div className="flex flex-wrap gap-2">{actions}</div></div>;
}
