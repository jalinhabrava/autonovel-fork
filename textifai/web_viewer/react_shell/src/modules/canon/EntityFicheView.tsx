import React, { useEffect, useRef } from 'react';
import { MDXEditor, MDXEditorMethods, headingsPlugin, listsPlugin, quotePlugin, thematicBreakPlugin, markdownShortcutPlugin } from '@mdxeditor/editor';
import { t } from '../../i18n/ui';

export type EntityFicheViewProps = {
  editorKey: string;
  bodyMarkdown: string;
  onChangeBody: (next: string) => void;
  localDirty: boolean;
};

type EditorBoundaryProps = {
  children: React.ReactNode;
  fallback: React.ReactNode;
};

type EditorBoundaryState = {
  hasError: boolean;
};

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

export function EntityFicheView({ editorKey, bodyMarkdown, onChangeBody, localDirty }: EntityFicheViewProps) {
  const editorRef = useRef<MDXEditorMethods | null>(null);

  useEffect(() => {
    const markdown = bodyMarkdown || t('graph.fiche_empty_placeholder');
    const current = editorRef.current?.getMarkdown?.() || '';
    if (current !== markdown) editorRef.current?.setMarkdown(markdown);
  }, [bodyMarkdown]);

  return (
    <section className="mt-5 rounded-2xl border border-neutral-200 bg-white p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-neutral-900">{t('graph.fiche_body')}</h3>
      </div>
      <p className="mb-3 text-xs text-neutral-500">{t('graph.fiche_local_note')}</p>
      {localDirty ? <div className="mb-3 text-xs text-amber-700">{t('graph.fiche_local_dirty')}</div> : null}
      <div className="min-h-[560px] overflow-auto rounded-2xl border border-neutral-200 bg-white p-2">
        <EditorBoundary
          fallback={<textarea value={bodyMarkdown || t('graph.fiche_empty_placeholder')} onChange={(event) => onChangeBody(event.target.value)} className="min-h-[380px] w-full rounded-xl border border-neutral-200 bg-neutral-50 p-3 text-sm leading-6 text-neutral-800" />}
        >
          <MDXEditor
            key={editorKey}
            ref={editorRef}
            markdown={bodyMarkdown || t('graph.fiche_empty_placeholder')}
            onChange={onChangeBody}
            plugins={[headingsPlugin(), listsPlugin(), quotePlugin(), thematicBreakPlugin(), markdownShortcutPlugin()]}
          />
        </EditorBoundary>
      </div>
    </section>
  );
}
