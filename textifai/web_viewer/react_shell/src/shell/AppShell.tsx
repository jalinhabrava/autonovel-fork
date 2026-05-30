import React, { useState } from 'react';
import { ChevronDown, X } from 'lucide-react';
import { StatusChip } from '../common/ui';
import { t } from '../i18n/ui';
import { screens, type SectionId } from './navigation';

function BrandMark() {
  const [logoFailed, setLogoFailed] = useState(false);
  const FULL_LOGO_SRC = '/branding/textifai-logo-full.png';
  if (!logoFailed) return <img src={FULL_LOGO_SRC} alt="TextifAI" className="h-8 w-auto object-contain" onError={() => setLogoFailed(true)} />;
  return <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-neutral-900 text-sm font-semibold text-white">T</div><div className="text-xl font-bold tracking-tight">TextifAI</div></div>;
}

function SettingsModal({ onClose }: { onClose: () => void }) {
  return <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4"><div className="w-full max-w-2xl rounded-3xl border border-neutral-200 bg-white shadow-2xl"><div className="flex items-center justify-between border-b border-neutral-200 p-5"><div><h2 className="text-lg font-semibold">{t('shell.settings')}</h2><p className="text-sm text-neutral-500">{t('shell.settings_note')}</p></div><button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-neutral-100"><X size={18} /></button></div></div></div>;
}

function SidebarNav({ active, setActive }: { active: SectionId; setActive: (id: SectionId) => void }) {
  return <><nav className="space-y-1">{screens.map((screen) => { const Icon = screen.icon; const selected = active === screen.id; return <button key={screen.id} onClick={() => setActive(screen.id)} className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left text-sm transition ${selected ? 'bg-neutral-900 text-white' : 'text-neutral-700 hover:bg-neutral-200'}`}><Icon size={17} /><span>{t(screen.label)}</span></button>; })}</nav><div className="mt-5 rounded-3xl bg-white border border-neutral-200 p-4 text-xs text-neutral-500"><b className="text-neutral-900">{t('shell.local_first')}</b><br />{t('shell.local_first_note')}</div></>;
}

export function AppShell({ active, setActive, children }: { active: SectionId; setActive: (id: SectionId) => void; children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  return <div className="min-h-screen h-screen bg-neutral-100 text-neutral-900 p-2 md:p-4 overflow-hidden"><div className="mx-auto w-full max-w-none h-full rounded-3xl bg-white shadow-xl overflow-hidden border border-neutral-200"><header className="flex items-center justify-between border-b border-neutral-200 px-5 py-4 bg-neutral-50"><button type="button" onClick={() => setActive('overview')} className="text-left"><BrandMark /><div className="text-xs text-neutral-500">{t('shell.tagline')}</div></button><div className="flex items-center gap-2 text-xs"><StatusChip>{t('shell.status.local_project')}</StatusChip><StatusChip>{t('shell.status.vaerl_ready')}</StatusChip></div></header><div className="grid grid-cols-12 h-[calc(100%-73px)] min-h-0"><aside className="col-span-12 md:col-span-2 border-r border-neutral-200 bg-neutral-50 p-3 flex min-h-0 flex-col"><SidebarNav active={active} setActive={setActive} /><div className="mt-auto pt-4 relative">{menuOpen ? <div className="absolute bottom-16 left-0 right-0 z-20 rounded-2xl border border-neutral-200 bg-white p-2 shadow-xl text-sm"><button type="button" onClick={() => { setSettingsOpen(true); setMenuOpen(false); }} className="w-full rounded-xl px-3 py-2 text-left hover:bg-neutral-100">{t('shell.settings')}</button><button type="button" onClick={() => setActive('hub')} className="w-full rounded-xl px-3 py-2 text-left hover:bg-neutral-100">{t('shell.menu.project_workspace')}</button><button type="button" className="w-full rounded-xl px-3 py-2 text-left text-neutral-500" disabled>{t('shell.menu.dev_tools_pending')}</button></div> : null}<button type="button" onClick={() => setMenuOpen((v) => !v)} className="w-full rounded-2xl border border-neutral-200 bg-white p-3 text-left hover:bg-neutral-100"><div className="flex items-center gap-2.5"><div className="shrink-0 flex h-9 w-9 items-center justify-center rounded-full bg-neutral-900 text-white font-semibold">A</div><div className="min-w-0 flex-1 leading-tight"><div className="truncate text-sm font-semibold">{t('shell.author_local')}</div><div className="truncate whitespace-nowrap text-xs text-neutral-500">{t('shell.workspace_private')}</div></div><ChevronDown size={16} className="shrink-0" /></div></button></div></aside><main className="col-span-12 md:col-span-10 bg-white min-h-0 overflow-y-auto">{children}</main></div></div>{settingsOpen ? <SettingsModal onClose={() => setSettingsOpen(false)} /> : null}</div>;
}
