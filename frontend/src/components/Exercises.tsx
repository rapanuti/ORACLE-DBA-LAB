import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { api, ApiError, save, ScriptResponse, SESSION_ID, store } from "../api";
import { registerOracleCompletion, monaco } from "../monacoSetup";
import { ResultsPanel } from "./ResultsPanel";
import { ErrorBox } from "./common";

interface Exercise { id: string; level: number; topic: string; title: string; explanation: string; task: string; hint: string; starter: string; validation_type: string; has_cleanup: boolean }
interface RunResult extends ScriptResponse { passed: boolean; checks: { ok: boolean; message: string }[] }

const LEVELS: Record<number, string> = { 1: "Nivel 1 · Consultas básicas", 2: "Nivel 2 · JOIN y agregación", 3: "Nivel 3 · DML, transacciones y DDL", 4: "Nivel 4 · PL/SQL" };

export function Exercises({ theme, onTx }: { theme: string; onTx: (p: boolean) => void }) {
  const [list, setList] = useState<Exercise[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, boolean>>(() => store("exercises-done", {}));
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [solution, setSolution] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const edRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  useEffect(() => {
    api.get<Exercise[]>("/api/exercises").then((l) => { setList(l); setSel((s) => s ?? l.find((e) => !store<Record<string, boolean>>("exercises-done", {})[e.id])?.id ?? l[0]?.id); }).catch(setErr);
  }, []);

  const ex = list.find((e) => e.id === sel);
  useEffect(() => { setResult(null); setShowHint(false); setSolution(null); setNotice(null); }, [sel]);

  const draftKey = (id: string) => `exercise-draft-${id}`;
  const run = async () => {
    if (!ex || !edRef.current) return;
    const sql = edRef.current.getValue();
    setRunning(true); setErr(null); setNotice(null);
    try {
      const r = await api.post<RunResult>(`/api/exercises/${ex.id}/run`, { session_id: SESSION_ID, sql });
      setResult(r);
      onTx(r.transaction_pending);
      if (r.passed) {
        const d = { ...done, [ex.id]: true };
        setDone(d); save("exercises-done", d);
      }
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 409 ? new Error("Este ejercicio no necesita operaciones destructivas; revisa tu script.") : e);
    } finally { setRunning(false); }
  };

  const cleanup = async () => {
    if (!ex) return;
    const r = await api.post<{ message: string }>(`/api/exercises/${ex.id}/cleanup`, { session_id: SESSION_ID, sql: "" });
    setNotice(r.message);
  };

  const completed = Object.values(done).filter(Boolean).length;
  return (
    <div className="exercises">
      <aside className="ex-list">
        <div className="progress">
          <b>Progreso: {completed}/{list.length}</b>
          <div className="bar"><div style={{ width: `${list.length ? (completed / list.length) * 100 : 0}%` }} /></div>
        </div>
        {[1, 2, 3, 4].map((lvl) => (
          <div key={lvl}>
            <div className="ex-level">{LEVELS[lvl]}</div>
            {list.filter((e) => e.level === lvl).map((e) => (
              <button key={e.id} className={`ex-item ${e.id === sel ? "active" : ""}`} onClick={() => setSel(e.id)}>
                <span className={done[e.id] ? "ok" : "muted"}>{done[e.id] ? "✔" : "○"}</span> {e.title}
              </button>
            ))}
          </div>
        ))}
        <button className="link small" onClick={() => { setDone({}); save("exercises-done", {}); }}>Reiniciar progreso</button>
      </aside>
      {ex ? (
        <section className="ex-main">
          <div className="ex-desc">
            <div className="muted small">{LEVELS[ex.level]} · {ex.topic}</div>
            <h2>{ex.title} {done[ex.id] && <span className="badge ok">Completado</span>}</h2>
            <p className="explanation">📘 {ex.explanation}</p>
            <p className="task"><b>Tarea:</b> {ex.task}</p>
            <div className="ex-actions">
              <button className="primary" onClick={run} disabled={running}>{running ? "Validando…" : "▶ Ejecutar y validar"}</button>
              <button onClick={() => setShowHint((s) => !s)}>💡 Pista</button>
              <button onClick={async () => setSolution((await api.get<{ solution: string }>(`/api/exercises/${ex.id}/solution`)).solution)}>Ver solución</button>
              <button onClick={() => { edRef.current?.setValue(ex.starter); save(draftKey(ex.id), ex.starter); }}>Restablecer código</button>
              {ex.has_cleanup && <button onClick={cleanup} title="Elimina los objetos creados en este ejercicio">Limpiar objetos</button>}
            </div>
            {showHint && <div className="alert info">💡 {ex.hint}</div>}
            {solution && <pre className="solution">{solution}</pre>}
            {notice && <div className="alert info">{notice}</div>}
          </div>
          <ErrorBox error={err} />
          {result && (
            <div className={`validation ${result.passed ? "pass" : "fail"}`}>
              <b>{result.passed ? "✔ ¡Correcto! Ejercicio superado." : "✖ Aún no. Revisa las comprobaciones:"}</b>
              <ul>{result.checks.map((c, i) => <li key={i} className={c.ok ? "ok" : "bad"}>{c.ok ? "✔" : "✖"} {c.message}</li>)}</ul>
            </div>
          )}
          <div className="ex-editor">
            <Editor key={ex.id} defaultLanguage="sql" defaultValue={store<string>(draftKey(ex.id), ex.starter)} theme={theme === "dark" ? "vs-dark" : "vs"}
              onMount={(ed) => {
                edRef.current = ed;
                registerOracleCompletion();
                ed.addAction({ id: "ex-run", label: "Ejecutar y validar", keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter], run: () => { run(); } });
                ed.onDidChangeModelContent(() => save(draftKey(ex.id), ed.getValue()));
              }}
              options={{ minimap: { enabled: false }, fontSize: 14, automaticLayout: true, scrollBeyondLastLine: false }} />
          </div>
          <ResultsPanel response={result} />
        </section>
      ) : <div className="pad muted">Cargando ejercicios…</div>}
    </div>
  );
}
