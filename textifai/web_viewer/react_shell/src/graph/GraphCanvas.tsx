import React, { useCallback, useMemo, useRef, useState } from 'react';
import ForceGraph2D, { ForceGraphMethods, LinkObject, NodeObject } from 'react-force-graph-2d';
import { GraphCanvasEdge, GraphCanvasNode } from './types';

type ForceNode = GraphCanvasNode & NodeObject<GraphCanvasNode>;
type ForceLink = GraphCanvasEdge & LinkObject<GraphCanvasNode, GraphCanvasEdge>;

export type GraphCanvasProps = {
  nodes: GraphCanvasNode[];
  edges: GraphCanvasEdge[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
};

const LINK_COLOR = 'rgba(163, 163, 163, 0.45)';
const ACTIVE_LINK_COLOR = 'rgba(23, 23, 23, 0.7)';
const LABEL_ZOOM_THRESHOLD = 1.35;
const CENTER_ZOOM_LEVEL = 2.25;
const ANIMATION_MS = 450;

export function GraphCanvas({ nodes, edges, selectedNodeId, onSelectNode }: GraphCanvasProps) {
  const graphRef = useRef<ForceGraphMethods<GraphCanvasNode, GraphCanvasEdge>>();
  const [zoomLevel, setZoomLevel] = useState(1);

  const graphData = useMemo(
    () => ({
      nodes: nodes.map((node) => ({ ...node })),
      links: edges.map((edge) => ({ ...edge })),
    }),
    [edges, nodes],
  );

  const selectedNeighborIds = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const ids = new Set<string>([selectedNodeId]);
    edges.forEach((edge) => {
      if (edge.source === selectedNodeId) ids.add(edge.target);
      if (edge.target === selectedNodeId) ids.add(edge.source);
    });
    return ids;
  }, [edges, selectedNodeId]);

  const paintNode = useCallback(
    (node: ForceNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const isSelected = node.id === selectedNodeId;
      const isNeighbor = selectedNeighborIds.has(String(node.id));
      const radius = Math.max(6, 6 + Math.min(node.degree || node.relationshipCount || 0, 10) * 0.55);

      ctx.save();

      if (isSelected) {
        ctx.beginPath();
        ctx.arc(x, y, radius + 6, 0, Math.PI * 2, false);
        ctx.fillStyle = 'rgba(37, 99, 235, 0.16)';
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2, false);
      ctx.fillStyle = node.color;
      ctx.fill();

      ctx.lineWidth = isSelected ? 2.75 : isNeighbor ? 1.75 : 1.25;
      ctx.strokeStyle = isSelected ? '#111827' : '#ffffff';
      ctx.stroke();

      if (isSelected) {
        ctx.beginPath();
        ctx.arc(x, y, radius + 3, 0, Math.PI * 2, false);
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = '#2563eb';
        ctx.stroke();
      }

      const showLabel = isSelected || globalScale >= LABEL_ZOOM_THRESHOLD || zoomLevel >= LABEL_ZOOM_THRESHOLD;
      if (showLabel) {
        const fontSize = Math.max(10, 13 / globalScale);
        const paddingX = 6 / globalScale;
        const paddingY = 3 / globalScale;
        const labelX = x + radius + 6 / globalScale;
        const labelY = y;

        ctx.font = `${fontSize}px Inter, ui-sans-serif, system-ui, sans-serif`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        const metrics = ctx.measureText(node.label);
        const boxWidth = metrics.width + paddingX * 2;
        const boxHeight = fontSize + paddingY * 2;

        ctx.fillStyle = 'rgba(255, 255, 255, 0.88)';
        ctx.fillRect(labelX, labelY - boxHeight / 2, boxWidth, boxHeight);
        ctx.fillStyle = '#171717';
        ctx.fillText(node.label, labelX + paddingX, labelY);
      }

      ctx.restore();
    },
    [selectedNeighborIds, selectedNodeId, zoomLevel],
  );

  const paintPointerArea = useCallback((node: ForceNode, color: string, ctx: CanvasRenderingContext2D) => {
    const radius = Math.max(8, 8 + Math.min(node.degree || node.relationshipCount || 0, 10) * 0.55);
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, Math.PI * 2, false);
    ctx.fill();
  }, []);

  const handleNodeDragEnd = useCallback((node: ForceNode) => {
    node.fx = node.x;
    node.fy = node.y;
  }, []);

  const handleNodeRightClick = useCallback((node: ForceNode, event: MouseEvent) => {
    event.preventDefault();
    onSelectNode(String(node.id));
    graphRef.current?.centerAt(node.x ?? 0, node.y ?? 0, ANIMATION_MS);
    graphRef.current?.zoom(CENTER_ZOOM_LEVEL, ANIMATION_MS);
  }, [onSelectNode]);

  return (
    <div className="h-full min-h-[560px] w-full overflow-hidden rounded-3xl border border-neutral-200 bg-white">
      <ForceGraph2D<GraphCanvasNode, GraphCanvasEdge>
        ref={graphRef}
        graphData={graphData}
        nodeId="id"
        linkSource="source"
        linkTarget="target"
        backgroundColor="#ffffff"
        nodeRelSize={6}
        autoPauseRedraw={false}
        minZoom={0.4}
        maxZoom={6}
        cooldownTicks={120}
        linkColor={(link) => {
          const sourceId = typeof link.source === 'object' ? String(link.source.id) : String(link.source);
          const targetId = typeof link.target === 'object' ? String(link.target.id) : String(link.target);
          return selectedNodeId && (sourceId === selectedNodeId || targetId === selectedNodeId) ? ACTIVE_LINK_COLOR : LINK_COLOR;
        }}
        linkWidth={(link) => {
          const sourceId = typeof link.source === 'object' ? String(link.source.id) : String(link.source);
          const targetId = typeof link.target === 'object' ? String(link.target.id) : String(link.target);
          return selectedNodeId && (sourceId === selectedNodeId || targetId === selectedNodeId) ? 2.2 : 1.1;
        }}
        nodeCanvasObjectMode={() => 'replace'}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={paintPointerArea}
        onNodeClick={(node) => onSelectNode(String(node.id))}
        onBackgroundClick={() => onSelectNode(null)}
        onNodeDragEnd={handleNodeDragEnd}
        onNodeRightClick={handleNodeRightClick}
        onZoom={({ k }) => setZoomLevel(k)}
      />
    </div>
  );
}

export default GraphCanvas;
