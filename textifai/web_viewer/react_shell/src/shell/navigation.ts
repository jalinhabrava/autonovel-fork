import { BookOpen, Upload, Inbox, GitBranch, Network, PenLine, MessageSquareText } from 'lucide-react';
import type { UiI18nKey } from '../i18n/ui';
import React from 'react';

export type SectionId = 'hub' | 'ingest' | 'review' | 'graph' | 'codex' | 'editor' | 'story' | 'ask' | 'overview';
export type ScreenConfig = { id: SectionId; label: UiI18nKey; icon: React.ComponentType<{ size?: number; className?: string }> };

export const screens: ScreenConfig[] = [
  { id: 'hub', label: 'nav.hub', icon: BookOpen },
  { id: 'ingest', label: 'nav.ingest', icon: Upload },
  { id: 'review', label: 'nav.review', icon: Inbox },
  { id: 'graph', label: 'nav.graph', icon: GitBranch },
  { id: 'codex', label: 'nav.codex', icon: Network },
  { id: 'editor', label: 'nav.editor', icon: PenLine },
  { id: 'ask', label: 'nav.ask', icon: MessageSquareText },
];
