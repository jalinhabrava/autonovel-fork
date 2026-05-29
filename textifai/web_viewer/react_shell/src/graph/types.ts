export type GraphKind = 'chapter' | 'character' | 'concept' | 'event' | 'object' | 'place' | 'review' | 'unresolved' | 'note';

export type GraphCanvasNode = {
  id: string;
  label: string;
  kind: GraphKind;
  reviewState: string;
  notePath: string;
  summaryExcerpt: string;
  aliases?: string[];
  backlinks?: string[];
  outgoingWikilinks?: Array<{ target?: string; label?: string }>;
  evidenceCount?: number;
  reviewCount?: number;
  relationshipCount: number;
  degree: number;
  color: string;
};

export type GraphCanvasEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
};

export type GraphViewModel = {
  nodes: GraphCanvasNode[];
  edges: GraphCanvasEdge[];
  kinds: GraphKind[];
  byId: Record<string, GraphCanvasNode>;
};
