import { useEffect, useState } from "react";
import { api } from "../api";
import { DataGrid, ErrorBox } from "./common";

interface Section { id: string; description: string; sql: string }
interface SectionData { columns: string[]; rows: unknown[][]; sql: string; description: string }

export function AdminView() {
  const [index, setIndex] = useState<{ enabled: boolean; user: string; sections: Section[] } | null>(null);
  const [sel, setSel] = useState("instance");
  const [data, setData] = useState<SectionData | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [showSql, setShowSql] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => { api.get<any>("/api/admin").then(setIndex).catch(setErr); }, []);
  useEffect(() => {
    setData(null); setErr(null);
    api.get<SectionData>(`/api/admin/${sel}`).then(setData).catch(setErr);
  }, [sel, tick]);

  if (index && !index.enabled) return <div className="pad alert warn">Funciones administrativas deshabilitadas (ADMIN_ENABLED=false).</div>;
  const kv = sel === "instance" && data?.rows.length === 1;
  return (
    <div className="admin">
      <div className="alert info small">
        🛡 Vista administrativa de <b>solo lectura</b> sobre la base <b>local</b>, conectada como <b>{index?.user ?? "SYSTEM"}</b>.
        Está separada del editor SQL: desde aquí no se puede ejecutar SQL arbitrario con privilegios de DBA.
      </div>
      <div className="admin-body">
        <nav className="admin-nav">
          {index?.sections.map((s) => (
            <button key={s.id} className={s.id === sel ? "active" : ""} onClick={() => setSel(s.id)} title={s.description}>{s.description.split(" (")[0]}</button>
          ))}
        </nav>
        <section className="admin-main">
          <div className="toolbar">
            <b>{data?.description}</b><div className="spacer" />
            <button onClick={() => setShowSql((s) => !s)}>{showSql ? "Ocultar SQL" : "Ver SQL usado"}</button>
            <button onClick={() => setTick((t) => t + 1)}>⟳ Actualizar</button>
          </div>
          {showSql && data && <pre className="solution">{data.sql}</pre>}
          <ErrorBox error={err} />
          {!data && !err && <div className="muted pad">Cargando…</div>}
          {data && kv && (
            <table className="grid compact kv"><tbody>
              {data.columns.map((c, i) => <tr key={c}><th>{c}</th><td>{String(data.rows[0][i] ?? "")}</td></tr>)}
            </tbody></table>
          )}
          {data && !kv && <DataGrid columns={data.columns.map((name) => ({ name }))} rows={data.rows} />}
        </section>
      </div>
    </div>
  );
}
