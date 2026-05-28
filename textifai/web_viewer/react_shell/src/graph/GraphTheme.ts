import { GraphKind } from './types';

const GRAPH_KIND_COLORS: Record<GraphKind, string> = {
  chapter: '#7f7a6a',
  character: '#111827',
  concept: '#6b7280',
  event: '#9a3412',
  object: '#0f766e',
  place: '#1d4ed8',
  review: '#b91c1c',
  unresolved: '#9333ea',
  note: '#525252',
};

export function pickColor(kind: GraphKind): string {
  return GRAPH_KIND_COLORS[kind];
}
