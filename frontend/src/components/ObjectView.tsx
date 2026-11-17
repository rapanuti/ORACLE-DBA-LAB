import { useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import { api } from "../api";
import type { ObjRef } from "./ObjectExplorer";
import { DataGrid, ErrorBox, fmt, Tabs } from "./common";

type Sub = "structure" | "data" | "ddl";

export function ObjectView({ obj, profile, theme, onSendToEditor }: {
  obj: ObjRef; profile: string; theme: string; onSendToEditor: (sql: string) => void;
}) {
  const tabular = obj.type === "TABLE" || obj.type === "VIEW";
  const [sub, setSub] = useState<Sub>(tabular ? "structure" : "ddl");
  useEffect(() => setSub(tabular ? "structure" : "ddl"), [obj.name, obj.type, tabular]);

  const tabs: { id: Sub; label: string }[] = tabular
    ? [{ id: "structure", label: "Estructura" }, { id: "data", label: "Datos" }, { id: "ddl", label: "DDL" }]
    : [{ id: "structure", label: "Detalles" }, { id: "ddl", label: "Código / DDL" }];

  const q = `${obj.schema.toLowerCase()}.${obj.name.toLowerCase()}`;
  return (
    <div className="object-view">
      <div className="object-head">
        <h2><span className="otype">{obj.type}</span> {obj.schema}.{obj.name}</h2>
        <div className="spacer" />
        {tabular && <button onClick={() => onSendToEditor(`SELECT *\nFROM ${q}\nFETCH FIRST 100 ROWS ONLY;`)}>Consultar en editor</button>}
        {(obj.type === "FUNCTION") && <button onClick={() => onSendToEditor(`SELECT ${q}(/* argumentos */) FROM dual;`)}>Probar en editor</button>}
        {(obj.type === "PROCEDURE" || obj.type === "PACKAGE") && <button onClick={() => onSendToEditor(`BEGIN\n  ${q}${obj.type === "PACKAGE" ? ".subprograma" : ""}(/* argumentos */);\nEND;\n/`)}>Probar en editor</button>}
        {obj.type === "SEQUENCE" && <button onClick={() => onSendToEditor(`SELECT ${q}.NEXTVAL FROM dual;`)}>NEXTVAL en editor</button>}
      </div>
      <Tabs tabs={tabs} value={sub} onChange={setSub} />
      <div className="object-body">
        {sub === "structure" && (tabular ? <TableStructure obj={obj} profile={profile} /> : <ObjectDetails obj={obj} profile={profile} />)}
        {sub === "data" && <TableData obj={obj} profile={profile} />}
        {sub === "ddl" && <Ddl obj={obj} profile={profile} theme={theme} />}
      </div>
    </div>
  );
}

const CONS: Record<string, string> = { P: "PRIMARY KEY", U: "UNIQUE", R: "FOREIGN KEY", C: "CHECK" };

function TableStructure({ obj, profile }: { obj: ObjRef; profile: string }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    setD(null);
    api.get("/api/explorer/table", { profile, schema: obj.schema, name: obj.name }).then(setD).catch(setErr);
  }, [obj.schema, obj.name, profile]);
  if (err) return <ErrorBox error={err} />;
  if (!d) return <div className="muted pad">Cargando…</div>;
  const pk = new Set(d.constraints.filter((c: any) => c.constraint_type === "P").flatMap((c: any) => c.columns.split(", ")));
  const fk = new Set(d.constraints.filter((c: any) => c.constraint_type === "R").flatMap((c: any) => c.columns.split(", ")));
  return (
    <div className="structure">
      {d.comment && <p className="comment">💬 {d.comment}</p>}
      <div className="stats">
        <span>Filas: <b>{d.stats.row_count ?? d.stats.num_rows ?? "?"}</b></span>
        {d.stats.blocks != null && <span>Bloques: <b>{d.stats.blocks}</b></span>}
        {d.stats.last_analyzed && <span>Estadísticas: <b>{d.stats.last_analyzed}</b></span>}
      </div>
      <h4>Columnas</h4>
      <table className="grid compact">
        <thead><tr><th>#</th><th>Columna</th><th>Tipo</th><th>Nulo</th><th>Default</th><th>Clave</th><th>Comentario</th></tr></thead>
        <tbody>
          {d.columns.map((c: any) => (
            <tr key={c.column_name}>
              <td className="rownum">{c.column_id}</td>
              <td><b>{c.column_name}</b></td>
              <td><code>{c.type_display}</code>{c.identity_column === "YES" && <span className="tag">IDENTITY</span>}</td>
              <td>{c.nullable === "Y" ? "Sí" : <b>NOT NULL</b>}</td>
              <td><code>{c.identity_column === "YES" ? "" : fmt(c.data_default)}</code></td>
              <td>{pk.has(c.column_name) && <span className="tag pk">PK</span>}{fk.has(c.column_name) && <span className="tag fk">FK</span>}</td>
              <td className="muted">{c.comments}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>Restricciones</h4>
      <table className="grid compact">
        <thead><tr><th>Nombre</th><th>Tipo</th><th>Columnas</th><th>Detalle</th><th>Estado</th></tr></thead>
        <tbody>
          {d.constraints.map((c: any) => (
            <tr key={c.constraint_name}>
              <td>{c.constraint_name}</td><td><span className={`tag c${c.constraint_type}`}>{CONS[c.constraint_type] ?? c.constraint_type}</span></td>
              <td>{c.columns}</td>
              <td><code>{c.constraint_type === "R" ? `→ ${c.r_table} (${c.r_columns})${c.delete_rule !== "NO ACTION" ? " ON DELETE " + c.delete_rule : ""}` : c.search_condition_vc ?? ""}</code></td>
              <td>{c.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {d.indexes.length > 0 && (<>
        <h4>Índices</h4>
        <table className="grid compact">
          <thead><tr><th>Nombre</th><th>Tipo</th><th>Unicidad</th><th>Columnas</th><th>Estado</th></tr></thead>
          <tbody>{d.indexes.map((i: any) => <tr key={i.index_name}><td>{i.index_name}</td><td>{i.index_type}</td><td>{i.uniqueness}</td><td>{i.columns}</td><td>{i.status}</td></tr>)}</tbody>
        </table>
      </>)}
      {d.triggers.length > 0 && (<>
        <h4>Triggers</h4>
        <table className="grid compact">
          <thead><tr><th>Nombre</th><th>Momento</th><th>Evento</th><th>Estado</th></tr></thead>
          <tbody>{d.triggers.map((t: any) => <tr key={t.trigger_name}><td>{t.trigger_name}</td><td>{t.trigger_type}</td><td>{t.triggering_event}</td><td>{t.status}</td></tr>)}</tbody>
        </table>
      </>)}
    </div>
  );
}

function TableData({ obj, profile }: { obj: ObjRef; profile: string }) {
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<{ col: string; desc: boolean } | null>(null);
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  const limit = 100;
  useEffect(() => { setPage(0); setSort(null); }, [obj.schema, obj.name]);
  useEffect(() => {
    setErr(null);
    api.get("/api/explorer/table/data", { profile, schema: obj.schema, name: obj.name, offset: page * limit, limit, order_by: sort?.col, desc: sort?.desc })
      .then(setD).catch(setErr);
  }, [obj.schema, obj.name, profile, page, sort]);
  if (err) return <ErrorBox error={err} />;
  if (!d) return <div className="muted pad">Cargando…</div>;
  return (
    <div className="table-data">
      <div className="pager">
        <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>◀</button>
        <span>Filas {page * limit + 1}–{page * limit + d.rows.length}</span>
        <button disabled={!d.has_more} onClick={() => setPage((p) => p + 1)}>▶</button>
        <span className="muted">Clic en una columna para ordenar</span>
      </div>
      <DataGrid columns={d.columns} rows={d.rows} sort={sort}
        onSort={(col) => { setPage(0); setSort((s) => (s?.col === col ? { col, desc: !s.desc } : { col, desc: false })); }} />
    </div>
  );
}

function ObjectDetails({ obj, profile }: { obj: ObjRef; profile: string }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    setD(null);
    api.get("/api/explorer/object", { profile, schema: obj.schema, name: obj.name, type: obj.type }).then(setD).catch(setErr);
  }, [obj.schema, obj.name, obj.type, profile]);
  if (err) return <ErrorBox error={err} />;
  if (!d) return <div className="muted pad">Cargando…</div>;
  const { object, subprograms, arguments: args, ...rest } = d;
  return (
    <div className="structure">
      <div className="stats">
        <span>Estado: <b className={object.status === "VALID" ? "ok" : "bad"}>{object.status}</b></span>
        <span>Creado: <b>{object.created}</b></span><span>Último DDL: <b>{object.last_ddl}</b></span>
      </div>
      {Object.keys(rest).length > 0 && (
        <table className="grid compact kv"><tbody>
          {Object.entries(rest).map(([k, v]) => <tr key={k}><th>{k}</th><td><code>{fmt(v)}</code></td></tr>)}
        </tbody></table>
      )}
      {args && args.length > 0 && (<>
        <h4>Parámetros</h4>
        <table className="grid compact">
          <thead><tr><th>Subprograma</th><th>Posición</th><th>Argumento</th><th>Tipo</th><th>Modo</th></tr></thead>
          <tbody>{args.map((a: any, i: number) => (
            <tr key={i}><td>{a.subprogram_name}</td><td>{a.position}</td><td>{a.argument_name ?? <i>(RETURN)</i>}</td><td>{a.data_type}</td><td>{a.in_out}</td></tr>
          ))}</tbody>
        </table>
      </>)}
      {subprograms && obj.type === "PACKAGE" && <p className="muted">Subprogramas: {subprograms.map((s: any) => s.procedure_name).join(", ")}</p>}
    </div>
  );
}

function Ddl({ obj, profile, theme }: { obj: ObjRef; profile: string; theme: string }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    setD(null);
    api.get("/api/explorer/ddl", { profile, schema: obj.schema, name: obj.name, type: obj.type }).then(setD).catch(setErr);
  }, [obj.schema, obj.name, obj.type, profile]);
  if (err) return <ErrorBox error={err} />;
  if (!d) return <div className="muted pad">Cargando…</div>;
  return (
    <div className="ddl">
      {d.errors?.length > 0 && (
        <div className="alert warn"><b>Errores de compilación</b>
          <ul>{d.errors.map((e: any, i: number) => <li key={i}>{e.type} línea {e.line}: {e.text}</li>)}</ul>
        </div>
      )}
      <div className="muted small">Generado con {d.source}</div>
      <div className="ddl-editor">
        <Editor language="sql" value={d.ddl} theme={theme === "dark" ? "vs-dark" : "vs"}
          options={{ readOnly: true, minimap: { enabled: false }, fontSize: 13, automaticLayout: true, scrollBeyondLastLine: false }} />
      </div>
    </div>
  );
}
