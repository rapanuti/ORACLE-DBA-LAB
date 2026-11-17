import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox } from "./common";

export interface ObjRef { schema: string; name: string; type: string }

const TYPE_LABEL: Record<string, string> = {
  TABLE: "Tablas", VIEW: "Vistas", INDEX: "Índices", SEQUENCE: "Secuencias", FUNCTION: "Funciones",
  PROCEDURE: "Procedimientos", PACKAGE: "Paquetes", TRIGGER: "Triggers", TYPE: "Tipos", SYNONYM: "Sinónimos",
};
const TYPE_ICON: Record<string, string> = {
  TABLE: "▦", VIEW: "◫", INDEX: "⚲", SEQUENCE: "#", FUNCTION: "ƒ", PROCEDURE: "⚙", PACKAGE: "▣", TRIGGER: "⚡", TYPE: "T", SYNONYM: "≡",
};

interface Group { type: string; items: { name: string; status: string }[] }

export function ObjectExplorer({ profile, refreshKey, selected, onSelect, schema, onSchema }: {
  profile: string; refreshKey: number; selected: ObjRef | null; onSelect: (o: ObjRef) => void;
  schema: string | null; onSchema: (s: string) => void;
}) {
  const [schemas, setSchemas] = useState<{ name: string; objects: number }[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [open, setOpen] = useState<Record<string, boolean>>({ TABLE: true, VIEW: true });
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<{ current: string; schemas: { name: string; objects: number }[] }>("/api/explorer/schemas", { profile })
      .then((r) => { setSchemas(r.schemas); if (!schema) onSchema(r.current); })
      .catch(setError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, refreshKey]);

  useEffect(() => {
    if (!schema) return;
    setLoading(true);
    setError(null);
    api.get<{ groups: Group[] }>("/api/explorer/objects", { profile, schema })
      .then((r) => setGroups(r.groups))
      .catch(setError)
      .finally(() => setLoading(false));
  }, [profile, schema, refreshKey]);

  const f = filter.trim().toUpperCase();
  return (
    <div className="explorer">
      <div className="explorer-head">
        <select value={schema ?? ""} onChange={(e) => onSchema(e.target.value)} aria-label="Esquema">
          {schemas.map((s) => <option key={s.name} value={s.name}>{s.name} ({s.objects})</option>)}
        </select>
        <input placeholder="Filtrar objetos…" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      <ErrorBox error={error} />
      {loading && <div className="muted pad">Cargando…</div>}
      <div className="tree">
        {groups.filter((g) => g.items.length).map((g) => {
          const items = g.items.filter((i) => !f || i.name.includes(f));
          const isOpen = open[g.type] || !!f;
          return (
            <div key={g.type} className="tree-group">
              <button className="tree-toggle" onClick={() => setOpen((o) => ({ ...o, [g.type]: !o[g.type] }))}>
                <span className="caret">{isOpen ? "▾" : "▸"}</span> {TYPE_LABEL[g.type] ?? g.type} <span className="count">{items.length}</span>
              </button>
              {isOpen && items.map((i) => {
                const active = selected?.name === i.name && selected?.type === g.type && selected?.schema === schema;
                return (
                  <button key={i.name} className={`tree-item ${active ? "active" : ""} ${i.status === "INVALID" ? "invalid" : ""}`}
                    onClick={() => onSelect({ schema: schema!, name: i.name, type: g.type })}
                    title={i.status === "INVALID" ? "Objeto INVÁLIDO: revisa errores de compilación" : i.name}>
                    <span className="ticon">{TYPE_ICON[g.type]}</span>{i.name}{i.status === "INVALID" && " ⚠"}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
