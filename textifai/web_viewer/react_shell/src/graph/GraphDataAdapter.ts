import { GraphPayload } from '../api';
import { GraphCanvasEdge, GraphCanvasNode, GraphKind, GraphViewModel } from './types';

const DEFAULT_KIND: GraphKind = 'note';

export function mapGraphPayload(payload: GraphPayload | null | undefined): GraphViewModel {
  const rawNodes = payload?.nodes || [];
  const rawEdges = payload?.edges || [];

  const nodes: GraphCanvasNode[] = rawNodes
    .filter((node) => Boolean(node.id))
    .map((node) => {
      const kind = normalizeKind(String(node.display_kind || node.kind || DEFAULT_KIND));
      return {
        id: String(node.id),
        label: String(node.label || node.id || ''),
        kind,
        reviewState: String(node.review_state || node.status || 'unknown'),
        notePath: String(node.note_path || node.canonical_note_path || ''),
        summaryExcerpt: String(node.summary_excerpt || ''),
        relationshipCount: Number(node.relationship_count || node.degree || 0),
        degree: Number(node.degree || node.canonical_degree || 0),
        color: pickColor(kind),
      };
    });

  const edges: GraphCanvasEdge[] = rawEdges
    .filter((edge) => edge.source && edge.target)
    .map((edge) => ({
      id: String(edge.id || `${edge.source}-${edge.target}`),
      source: String(edge.source),
      target: String(edge.target),
      label: String(edge.label || edge.type || ''),
    }));

  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const kinds = Array.from(new Set(nodes.map((node) => node.kind)));
  return { nodes, edges, kinds, byId };
}

export function filterGraph(vm: GraphViewModel, kind: string, query: string, relatedTo: string | null): GraphViewModel {
  const normalizedQuery = query.trim().toLowerCase();
  const kindFiltered = vm.nodes.filter((node) => (kind === 'all' ? true : node.kind === kind));
  const searchFiltered = kindFiltered.filter((node) => {
    if (!normalizedQuery) return true;
    return node.label.toLowerCase().includes(normalizedQuery) || node.notePath.toLowerCase().includes(normalizedQuery);
  });

  const visibleIds = new Set(searchFiltered.map((node) => node.id));
  if (relatedTo && visibleIds.has(relatedTo)) {
    const neighborIds = new Set<string>([relatedTo]);
    vm.edges.forEach((edge) => {
      if (edge.source === relatedTo) neighborIds.add(edge.target);
      if (edge.target === relatedTo) neighborIds.add(edge.source);
    });
    const relatedNodes = searchFiltered.filter((node) => neighborIds.has(node.id));
    const relatedIds = new Set(relatedNodes.map((node) => node.id));
    const relatedEdges = vm.edges.filter((edge) => relatedIds.has(edge.source) && relatedIds.has(edge.target));
    return { ...vm, nodes: relatedNodes, edges: relatedEdges, byId: Object.fromEntries(relatedNodes.map((n) => [n.id, n])) };
  }

  const edges = vm.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
  return { ...vm, nodes: searchFiltered, edges, byId: Object.fromEntries(searchFiltered.map((n) => [n.id, n])) };
}

function normalizeKind(kind: string): GraphKind {
  const value = kind.toLowerCase();
  if (['chapter', 'character', 'concept', 'event', 'object', 'place', 'review'].includes(value)) return value as GraphKind;
  return DEFAULT_KIND;
}

function pickColor(kind: GraphKind): string {
  const palette: Record<GraphKind, string> = {
    chapter: '#7f7a6a',
    character: '#111827',
    concept: '#6b7280',
    event: '#9a3412',
    object: '#0f766e',
    place: '#1d4ed8',
    review: '#b91c1c',
    note: '#525252',
  };
  return palette[kind];
}
