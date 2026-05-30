import React from 'react';

export function StatusChip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-neutral-200 bg-white px-3 py-1 text-neutral-600">{children}</span>;
}

export function Button({ children, variant = 'primary', disabled = false, onClick, ...rest }: { children: React.ReactNode; variant?: 'primary' | 'secondary'; disabled?: boolean; onClick?: () => void } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" disabled={disabled} onClick={onClick} className={`rounded-2xl px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${variant === 'primary' ? 'bg-neutral-900 text-white' : 'bg-neutral-100 text-neutral-800 border border-neutral-200'}`} {...rest}>{children}</button>;
}

export function Metric({ label, value, note }: { label: string; value: React.ReactNode; note: string }) {
  return <div className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm"><div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div><div className="mt-2 text-3xl font-semibold tracking-tight">{value}</div><p className="mt-2 text-sm text-neutral-500">{note}</p></div>;
}

export function TopBar({ title, subtitle, actions }: { title: string; subtitle: string; actions?: React.ReactNode }) {
  return <div className="flex flex-col gap-3 border-b border-neutral-200 bg-neutral-50 p-5 lg:flex-row lg:items-center lg:justify-between"><div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 text-sm text-neutral-500">{subtitle}</p></div><div className="flex flex-wrap gap-2">{actions}</div></div>;
}
