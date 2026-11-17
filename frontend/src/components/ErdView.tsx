import { useEffect, useMemo, useState } from "react";
import { Background, Controls, Edge, Handle, MarkerType, MiniMap, Node, NodeProps, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { api } from "../api";
import { ErrorBox } from "./common";

interface ErdCol { name: string; type: string; nullable: boolean; pk: boolean; fk: boolean }
interface ErdTable { name: string; columns: ErdCol[] }
interface ErdRel { name: string; from: string; to: string; columns: string[]; ref_columns: string[] }

const W = 250;
const ROW = 20;

function TableNode({ data }: NodeProps) {
  const t = data.table as ErdTable;
  return (
    <div className="erd-node">
      <Handle type="target" position={Position.Left} />
      <div className="erd-title" onDoubleClick={() => (data.onOpen as (n: string) => void)(t.name)} title="Doble clic: abrir tabla">{t.name}</div>
      {t.columns.map((c) => (
        <div key={c.name} className={`erd-col ${c.pk ? "pk" : ""}`}>
          <span>{c.pk ? "🔑 " : c.fk ? "🔗 " : ""}{c.name}{!c.nullable && !c.pk ? " *" : ""}</span>
          <span className="erd-type">{c.type}</span>
        </div>
      ))}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { table: TableNode };

export function ErdView({ profile, schema, theme, onOpenTable }: { profile: string; schema: string | null; theme: string; onOpenTable: (name: string) => void }) {
  const [data, setData] = useState<{ tables: ErdTable[]; relations: ErdRel[] } | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [hideMeta, setHideMeta] = useState(true);

  useEffect(() => {
    if (!schema) return;
    setData(null);
    api.get<{ tables: ErdTable[]; relations: ErdRel[] }>("/api/explorer/erd", { profile, schema }).then(setData).catch(setErr);
  }, [profile, schema]);

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as Node[], edges: [] as Edge[] };
    const hidden = new Set(hideMeta ? ["LAB_METADATA"] : []);
    const tables = data.tables.filter((t) => !hidden.has(t.name));
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "LR", nodesep: 30, ranksep: 90 });
    g.setDefaultEdgeLabel(() => ({}));
    tables.forEach((t) => g.setNode(t.name, { width: W, height: 30 + t.columns.length * ROW }));
    data.relations.forEach((r) => g.setEdge(r.to, r.from));
    dagre.layout(g);
    const nodes: Node[] = tables.map((t) => {
      const p = g.node(t.name);
      return { id: t.name, type: "table", position: { x: p.x - W / 2, y: p.y - p.height / 2 }, data: { table: t, onOpen: onOpenTable } };
    });
    const edges: Edge[] = data.relations.filter((r) => !hidden.has(r.from)).map((r) => ({
      id: r.name, source: r.to, target: r.from, label: r.columns.join(", "),
      markerEnd: { type: MarkerType.ArrowClosed }, style: { strokeWidth: 1.5 }, labelStyle: { fontSize: 10 },
    }));
    return { nodes, edges };
  }, [data, hideMeta, onOpenTable]);

  if (err) return <ErrorBox error={err} />;
  if (!data) return <div className="muted pad">Generando diagrama…</div>;
  return (
    <div className="erd">
      <div className="toolbar">
        <b>Diagrama entidad-relación · {schema}</b>
        <span className="muted">{data.tables.length} tablas · {data.relations.length} relaciones (FK). 🔑 PK · 🔗 FK · * NOT NULL. Doble clic en un título abre la tabla.</span>
        <div className="spacer" />
        <label><input type="checkbox" checked={hideMeta} onChange={(e) => setHideMeta(e.target.checked)} /> Ocultar LAB_METADATA</label>
      </div>
      <div className="erd-canvas">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.1} colorMode={theme === "dark" ? "dark" : "light"} nodesConnectable={false}>
          <Background />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </div>
    </div>
  );
}
