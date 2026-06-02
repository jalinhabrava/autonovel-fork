import React, { useEffect, useRef } from 'react';
import { MDXEditor, MDXEditorMethods, UndoRedo, BoldItalicUnderlineToggles, ListsToggle, CreateLink, BlockTypeSelect, Separator, toolbarPlugin, headingsPlugin, listsPlugin, quotePlugin, linkPlugin, linkDialogPlugin, thematicBreakPlugin, markdownShortcutPlugin } from '@mdxeditor/editor';
import { t } from '../../i18n/ui';

export type EntityFicheViewProps = {
  editorKey: string;
  bodyMarkdown: string;
  onChangeBody: (next: string) => void;
  onInternalLinkClick?: (href: string) => void;
  localDirty: boolean;
  saveState?: 'idle' | 'saving' | 'saved' | 'conflict' | 'error';
  saveMessage?: string;
  canSave?: boolean;
  onSave?: () => void;
  saveDisabledReason?: string;
};

type EditorBoundaryProps = {
  children: React.ReactNode;
  fallback: React.ReactNode;
};

type EditorBoundaryState = {
  hasError: boolean;
};

declare global {
  interface Window {
    __sp123bDebug?: Record<string, unknown>;
    __TEXTIFAI_FICHE_DEBUG__?: Record<string, unknown>;
  }
}

class EditorBoundary extends React.Component<EditorBoundaryProps, EditorBoundaryState> {
  constructor(props: EditorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): EditorBoundaryState {
    return { hasError: true };
  }

  componentDidUpdate(prevProps: EditorBoundaryProps): void {
    if (this.state.hasError && prevProps.children !== this.props.children) {
      this.setState({ hasError: false });
    }
  }

  componentDidCatch(): void {
    // keep graph surface alive even if MDXEditor runtime fails.
  }

  render(): React.ReactNode {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}

export function stripFrontmatter(markdown: string): { body: string; frontmatterHidden: boolean } {
  const source = String(markdown || '');
  if (!source.startsWith('---\n')) return { body: source, frontmatterHidden: false };
  const closing = source.indexOf('\n---\n', 4);
  if (closing === -1) return { body: source, frontmatterHidden: false };
  return { body: source.slice(closing + 5), frontmatterHidden: true };
}

function isInternalGraphSelectHref(href: string): boolean {
  return /(?:^|[?#&])graph_select=/.test(href);
}

function extractHrefFromEventTarget(target: EventTarget | null, path: EventTarget[] = []): string {
  const element = target as Node | null;
  if (!element) return '';
  const candidates = [element, ...path];
  for (const candidate of candidates) {
    if (!(candidate instanceof Element)) continue;
    const anchor = candidate.closest?.('a') as HTMLAnchorElement | null;
    const href = String(anchor?.getAttribute('href') || '').trim();
    if (href) return href;
  }
  let current: Node | null = element;
  while (current) {
    if (current instanceof Element) {
      const anchor = current.closest?.('a') as HTMLAnchorElement | null;
      const href = String(anchor?.getAttribute('href') || '').trim();
      if (href) return href;
    }
    current = current.parentNode;
  }
  return '';
}

export function EntityFicheView({ editorKey, bodyMarkdown, onChangeBody, onInternalLinkClick, localDirty, saveState = 'idle', saveMessage = '', canSave = false, onSave, saveDisabledReason = '' }: EntityFicheViewProps) {
  const editorRef = useRef<MDXEditorMethods | null>(null);
  const debugEnabled = !import.meta.env.PROD;

  useEffect(() => {
    const markdown = bodyMarkdown || t('graph.fiche_empty_placeholder');
    const current = editorRef.current?.getMarkdown?.() || '';
    if (current !== markdown) editorRef.current?.setMarkdown(markdown);
    if (debugEnabled) {
      window.__TEXTIFAI_FICHE_DEBUG__ = {
        ...(window.__TEXTIFAI_FICHE_DEBUG__ || {}),
        anchors_rendered_in_editor: Boolean(bodyMarkdown),
      };
    }
  }, [bodyMarkdown, debugEnabled]);

  useEffect(() => {
    if (!onInternalLinkClick) return undefined;
    const intercept = (event: MouseEvent) => {
      const path = typeof event.composedPath === 'function' ? event.composedPath() : [];
      const href = extractHrefFromEventTarget(event.target, path);
      if (!href || !isInternalGraphSelectHref(href)) return;
      event.preventDefault();
      event.stopPropagation();
      window.__sp123bDebug = {
        ...(window.__sp123bDebug || {}),
        docIntercepted: true,
        interceptedHref: href,
        interceptedEventType: event.type,
      };
      if (debugEnabled) {
        window.__TEXTIFAI_FICHE_DEBUG__ = {
          ...(window.__TEXTIFAI_FICHE_DEBUG__ || {}),
          link_click_events: [...((window.__TEXTIFAI_FICHE_DEBUG__?.link_click_events as string[]) || []), href],
        };
      }
      onInternalLinkClick(href);
    };
    document.addEventListener('click', intercept, true);
    document.addEventListener('mousedown', intercept, true);
    return () => {
      document.removeEventListener('click', intercept, true);
      document.removeEventListener('mousedown', intercept, true);
    };
  }, [onInternalLinkClick, debugEnabled]);

  return (
    <section className="mt-5 rounded-2xl border border-txf-border bg-txf-surface p-5" data-testid="entity-fiche-panel-body">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-txf-text">{t('graph.fiche_body')}</h3>
        <button type="button" data-testid="entity-fiche-save-button" onClick={onSave} disabled={!canSave || saveState === 'saving'} className={`rounded-xl border px-3 py-1.5 text-xs font-medium ${canSave && saveState !== 'saving' ? 'border-txf-border-strong bg-txf-surface text-txf-text hover:bg-txf-surface-soft' : 'border-txf-border bg-txf-surface-soft text-txf-subtle cursor-not-allowed'}`}>{saveState === 'saving' ? t('graph.fiche_saving') : t('graph.fiche_save')}</button>
      </div>
      <p className="mb-3 text-xs text-txf-subtle">{t('graph.fiche_local_note')}</p>
      {localDirty ? <div className="mb-3 text-xs text-txf-action">{t('graph.fiche_local_dirty')}</div> : null}
      {!canSave && saveDisabledReason ? <div className="mb-3 text-xs text-txf-subtle">{saveDisabledReason}</div> : null}
      {saveMessage ? <div data-testid="entity-fiche-save-status" className={`mb-3 rounded-xl border px-3 py-2 text-xs ${saveState === 'saved' ? 'border-txf-border bg-txf-surface-soft text-txf-text' : saveState === 'conflict' || saveState === 'error' ? 'border-txf-border bg-txf-surface-muted text-txf-text' : 'border-txf-border bg-txf-surface-soft text-txf-text'}`}>{saveMessage}</div> : null}
      <div
        className="entity-fiche-editor-shell min-h-[560px] overflow-auto rounded-2xl border border-txf-border bg-txf-surface p-2"
        data-testid="entity-fiche-editor"
        onClickCapture={(event) => {
          const href = extractHrefFromEventTarget(event.target);
          if (!href || !isInternalGraphSelectHref(href)) return;
          event.preventDefault();
          event.stopPropagation();
          onInternalLinkClick?.(href);
        }}
        onMouseDownCapture={(event) => {
          const href = extractHrefFromEventTarget(event.target);
          if (!href || !isInternalGraphSelectHref(href)) return;
          event.preventDefault();
          event.stopPropagation();
          onInternalLinkClick?.(href);
        }}
      >
        <EditorBoundary
          fallback={<textarea value={bodyMarkdown || t('graph.fiche_empty_placeholder')} onChange={(event) => onChangeBody(event.target.value)} className="min-h-[380px] w-full rounded-xl border border-txf-border bg-txf-surface-muted p-3 text-sm leading-6 text-txf-text" />}
        >
          <MDXEditor
            key={editorKey}
            ref={editorRef}
            className="entity-fiche-editor-root"
            contentEditableClassName="entity-fiche-editor-content"
            markdown={bodyMarkdown || t('graph.fiche_empty_placeholder')}
            onChange={onChangeBody}
            plugins={[
              toolbarPlugin({
                toolbarContents: () => (
                  <>
                    <UndoRedo />
                    <Separator />
                    <BoldItalicUnderlineToggles />
                    <Separator />
                    <BlockTypeSelect />
                    <Separator />
                    <ListsToggle />
                    <Separator />
                    <CreateLink />
                  </>
                ),
              }),
              headingsPlugin(),
              listsPlugin(),
              quotePlugin(),
              linkPlugin(),
              linkDialogPlugin(),
              thematicBreakPlugin(),
              markdownShortcutPlugin(),
            ]}
          />
        </EditorBoundary>
      </div>
    </section>
  );
}
