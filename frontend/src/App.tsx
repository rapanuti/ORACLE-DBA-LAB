import { useCallback, useEffect, useState } from "react";
import { api, Connection, save, SESSION_ID, store } from "./api";
import { refreshCompletion } from "./monacoSetup";
import { SqlWorkspace } from "./components/SqlWorkspace";
import { ObjectExplorer, ObjRef } from "./components/ObjectExplorer";
import { ObjectView } from "./components/ObjectView";
import { ErdView } from "./components/ErdView";
import { Exercises } from "./components/Exercises";
import { Compare } from "./components/Compare";
import { AdminView } from "./components/AdminView";
import { ConfirmDanger, Modal } from "./components/common";

type View = "sql" | "object" | "erd" | "exercises" | "compare" | "admin";

const VIEWS: { id: View; label: string }[] = [
  { id: "sql", label: "Editor SQL" },
  { id: "object", label: "Objeto" },
  { id: "erd", label: "Diagrama ER" },
  { id: "exercises", label: "Ejercicios" },
  { id: "compare", label: "PostgreSQL → Oracle" },
  { id: "admin", label: "Administración" },
];

interface ConnInfo { ok: boolean; version?: string; user?: string; container?: string; message?: string; code?: string }

export default function App() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [profile, setProfile] = useState<string>(() => store("profile", "lab"));
  const [info, setInfo] = useState<ConnInfo | null>(null);
  const [view, setView] = useState<View>("sql");
  const [selected, setSelected] = useState<ObjRef | null>(null);
  const [schema, setSchema] = useState<string | null>(null);
  const [txPending, setTxPending] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [injected, setInjected] = useState<{ sql: string; n: number } | null>(null);
  const [showReset, setShowReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [switchTo, setSwitchTo] = useState<string | null>(null);
  const [theme, setTheme] = useState<string>(() => store("theme", window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark"));
  const [labStatus, setLabStatus] = useState<{ allow_reset: boolean; reset_phrase: string } | null>(null);

  useEffect(() => { document.documentElement.dataset.theme = theme; save("theme", theme); }, [theme]);
  useEffect(() => {
    api.get<Connection[]>("/api/connections").then((c) => {
      setConnections(c);
      if (!c.some((x) => x.id === profile && x.editor)) setProfile("lab");
    }).catch(() => setInfo({ ok: false, message: "No se pudo contactar con el backend (¿está levantado en el puerto 8000?)" }));
    api.get<any>("/api/lab/status").then(setLabStatus).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    save("profile", profile);
    setInfo(null);
    setSchema(null);
    setSelected(null);
    api.post<ConnInfo>(`/api/connections/${profile}/test`).then(setInfo).catch((e) => setInfo({ ok: false, message: e.body?.message ?? e.message, code: e.body?.code }));
    api.get<{ transaction_pending: boolean }>(`/api/sql/session/${SESSION_ID}`, { profile })
      .then((r) => setTxPending(r.transaction_pending)).catch(() => {});
  }, [profile]);

  useEffect(() => { if (schema) refreshCompletion(profile, schema); }, [profile, schema, refreshKey]);

  const conn = connections.find((c) => c.id === profile);
  const editorConns = connections.filter((c) => c.editor);

  const onTx = useCallback((p: boolean) => { setTxPending(p); setRefreshKey((k) => k + 1); }, []);
  const sendToEditor = useCallback((sql: string) => { setInjected({ sql, n: Date.now() }); setView("sql"); }, []);
  const notify = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 5000); };

  const changeProfile = (id: string) => {
    if (txPending) setSwitchTo(id);
    else setProfile(id);
  };

  const doReset = async () => {
    setResetting(true);
    try {
      const r = await api.post<any>("/api/lab/reset", { confirm_text: labStatus?.reset_phrase ?? "RESTAURAR" });
      setTxPending(false);
      setRefreshKey((k) => k + 1);
      setShowReset(false);
      notify(`Esquema restaurado: ${Object.values(r.rows as Record<string, number>).reduce((a, b) => a + b, 0)} filas en ${(r.elapsed_ms / 1000).toFixed(1)} s`);
    } catch (e: any) {
      notify("Error al restaurar: " + e.message);
    } finally { setResetting(false); }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="logo">◉</span> Oracle DBA Lab</div>
        <select className={`conn-select ${conn?.kind ?? ""}`} value={profile} onChange={(e) => changeProfile(e.target.value)} aria-label="Conexión">
          {editorConns.map((c) => <option key={c.id} value={c.id}>{c.label}{c.writable ? "" : " — solo lectura"}</option>)}
        </select>
        <span className={`conn-status ${info?.ok ? "ok" : info ? "bad" : ""}`} title={info?.version ?? info?.message}>
          {info ? (info.ok ? `● ${info.user}@${info.container}` : `● Sin conexión`) : "○ Conectando…"}
        </span>
        {conn?.kind === "external" && <span className="badge ro" title="Base remota real">REMOTO{conn.writable ? " (ESCRITURA)" : " · SOLO LECTURA"}</span>}
        {txPending && <span className="badge warn" title="Hay cambios sin confirmar en tu sesión">Transacción pendiente</span>}
        <div className="spacer" />
        {profile === "lab" && labStatus?.allow_reset && (
          <button className="danger-outline" onClick={() => setShowReset(true)} title="Borra y recrea el esquema educativo">⟲ Restaurar estado inicial</button>
        )}
        <button className="icon" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Cambiar tema" aria-label="Cambiar tema">{theme === "dark" ? "☀" : "☾"}</button>
      </header>
      {info && !info.ok && (
        <div className="alert error banner">
          <b>No hay conexión con Oracle.</b> {info.code} {info.message}
          <div className="small">Comprueba que el contenedor esté sano: <code>docker compose ps</code>. La primera vez Oracle tarda 1–2 minutos en iniciar.</div>
        </div>
      )}
      <div className="main">
        <aside className="sidebar">
          <ObjectExplorer profile={profile} refreshKey={refreshKey} selected={selected} schema={schema} onSchema={setSchema}
            onSelect={(o) => { setSelected(o); setView("object"); }} />
        </aside>
        <section className="content">
          <nav className="viewtabs">
            {VIEWS.map((v) => (
              <button key={v.id} className={view === v.id ? "active" : ""} disabled={v.id === "object" && !selected} onClick={() => setView(v.id)}>
                {v.label}{v.id === "object" && selected ? `: ${selected.name}` : ""}
              </button>
            ))}
          </nav>
          <div className="view" style={{ display: view === "sql" ? "flex" : "none" }}>
            {conn && <SqlWorkspace key={profile} conn={conn} onTx={onTx} injected={injected} theme={theme} />}
          </div>
          {view === "object" && selected && <div className="view"><ObjectView obj={selected} profile={profile} theme={theme} onSendToEditor={sendToEditor} /></div>}
          {view === "erd" && <div className="view"><ErdView profile={profile} schema={schema} theme={theme} onOpenTable={(name) => { setSelected({ schema: schema!, name, type: "TABLE" }); setView("object"); }} /></div>}
          {view === "exercises" && <div className="view"><Exercises theme={theme} onTx={onTx} /></div>}
          {view === "compare" && <div className="view"><Compare theme={theme} onSendToEditor={sendToEditor} /></div>}
          {view === "admin" && <div className="view"><AdminView /></div>}
        </section>
      </div>
      {showReset && (
        <ConfirmDanger title="Restaurar el esquema educativo" phrase={labStatus?.reset_phrase ?? "RESTAURAR"} confirmLabel="Restaurar"
          busy={resetting} onCancel={() => setShowReset(false)} onConfirm={doReset}>
          <p>Se <b>eliminarán todos los objetos</b> del esquema <b>{conn?.user}</b> (incluidas tablas y funciones que hayas creado) y se recrearán las tablas de citas médicas con sus datos ficticios originales.</p>
          <p className="muted">Solo afecta al esquema del laboratorio local. Las transacciones abiertas se desharán.</p>
        </ConfirmDanger>
      )}
      {switchTo && (
        <Modal title="Transacción pendiente" onClose={() => setSwitchTo(null)}>
          <p>Tienes cambios sin confirmar en esta conexión. Siguen pendientes en su sesión si cambias de conexión (se descartan tras {30} min de inactividad).</p>
          <div className="modal-actions">
            <button onClick={() => setSwitchTo(null)}>Quedarme</button>
            <button className="primary" onClick={() => { setProfile(switchTo); setTxPending(false); setSwitchTo(null); }}>Cambiar igualmente</button>
          </div>
        </Modal>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
