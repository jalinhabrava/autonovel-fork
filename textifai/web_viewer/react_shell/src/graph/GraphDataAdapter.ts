import { GraphPayload } from '../api';
import { GraphCanvasEdge, GraphCanvasNode, GraphKind, GraphViewModel } from './types';
import { pickColor } from './GraphTheme';

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
        label: String(node.display_label || node.label || node.id || ''),
        kind,
        reviewState: String(node.review_state || node.status || 'unknown'),
        notePath: String(node.note_path || node.canonical_note_path || ''),
        summaryExcerpt: String(node.summary_excerpt || ''),
        aliases: Array.isArray(node.aliases) ? node.aliases.map(String) : [],
        backlinks: Array.isArray(node.backlinks) ? node.backlinks.map(String) : [],
        outgoingWikilinks: Array.isArray(node.outgoing_wikilinks) ? node.outgoing_wikilinks : [],
        evidenceCount: Number(node.evidence_count || 0),
        reviewCount: Number(node.review_count || 0),
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

export function filterGraph(vm: GraphViewModel, selectedKinds: Set<GraphKind> | GraphKind[] | 'all' | GraphKind, query: string, relatedTo: string | null): GraphViewModel {
  const normalizedQuery = query.trim().toLowerCase();
  const kindSet = selectedKinds === 'all'
    ? null
    : Array.isArray(selectedKinds)
      ? new Set(selectedKinds)
      : selectedKinds instanceof Set
        ? selectedKinds
        : new Set([selectedKinds]);
  const kindFiltered = vm.nodes.filter((node) => (!kindSet || kindSet.size === 0 ? true : kindSet.has(node.kind)));
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
  if (['chapter', 'character', 'concept', 'event', 'object', 'place', 'review', 'unresolved'].includes(value)) return value as GraphKind;
  return DEFAULT_KIND;
}
