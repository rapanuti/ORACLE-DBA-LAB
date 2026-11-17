import { useCallback, useEffect, useRef, useState } from "react";
import Editor, { OnMount } from "@monaco-editor/react";
import { api, ApiError, Connection, save, ScriptResponse, SESSION_ID, store } from "../api";
import { monaco, registerOracleCompletion } from "../monacoSetup";
import { ResultsPanel } from "./ResultsPanel";
import { Modal } from "./common";

interface HistoryItem { sql: string; at: string; ok: boolean; profile: string; ms: number }

interface Destructive { statements: { keyword: string; reason: string; line: number; preview: string }[]; profile: string }

const DEFAULT_SQL = `-- Bienvenido a Oracle DBA Lab. Esquema educativo: citas médicas (datos ficticios).
-- Ctrl/⌘+Enter ejecuta todo (o la selección). Ctrl/⌘+Shift+Enter ejecuta la sentencia bajo el cursor.

SELECT c.fecha_hora, p.nombres || ' ' || p.apellidos AS paciente,
       m.apellidos AS medico, e.nombre AS especialidad, c.estado
FROM   citas c
JOIN   pacientes p      ON p.id_paciente = c.id_paciente
JOIN   medicos m        ON m.id_medico = c.id_medico
JOIN   especialidades e ON e.id_especialidad = m.id_especialidad
WHERE  c.fecha_hora >= TRUNC(SYSDATE)
ORDER  BY c.fecha_hora
FETCH FIRST 20 ROWS ONLY;

BEGIN
  pkg_citas.resumen_medico(1);
  DBMS_OUTPUT.PUT_LINE('Citas de hoy: ' || pkg_citas.citas_del_dia);
END;
/
`;

export function useSqlRunner(profile: string, onTx: (pending: boolean) => void) {
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<ScriptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{ sql: string; info: Destructive } | null>(null);

  const run = useCallback(async (sql: string, confirm = false): Promise<ScriptResponse | null> => {
    if (!sql.trim()) return null;
    setRunning(true);
    setError(null);
    const t0 = performance.now();
    try {
      const res = await api.post<ScriptResponse>("/api/sql/execute", { session_id: SESSION_ID, profile, sql, confirm });
      setResponse(res);
      onTx(res.transaction_pending);
      const hist = store<HistoryItem[]>("history", []);
      save("history", [{ sql, at: new Date().toISOString(), ok: res.results.every((r) => r.status !== "error"), profile, ms: Math.round(performance.now() - t0) }, ...hist.filter((h) => h.sql !== sql)].slice(0, 100));
      return res;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.body?.error === "confirmation_required") {
        setPendingConfirm({ sql, info: e.body });
      } else if (e instanceof ApiError) {
        setError(e.message);
      } else setError(String(e));
      return null;
    } finally {
      setRunning(false);
    }
  }, [profile, onTx]);

  return { run, running, response, setResponse, error, pendingConfirm, setPendingConfirm };
}

export function DestructiveDialog({ info, onConfirm, onCancel }: { info: Destructive; onConfirm: () => void; onCancel: () => void }) {
  return (
    <Modal title="⚠ Confirmar operación destructiva" onClose={onCancel} tone="danger">
      <p>Conexión: <b>{info.profile}</b>. Las siguientes sentencias pueden borrar datos u objetos:</p>
      <ul className="danger-list">
        {info.statements.map((s, i) => (
          <li key={i}><b>Línea {s.line} · {s.keyword}</b> — {s.reason}<pre>{s.preview}</pre></li>
        ))}
      </ul>
      <p className="muted">Recuerda: DROP y TRUNCATE hacen COMMIT implícito y no se pueden deshacer con ROLLBACK. Puedes restaurar el esquema educativo desde la barra superior.</p>
      <div className="modal-actions">
        <button onClick={onCancel} autoFocus>Cancelar</button>
        <button className="danger" onClick={onConfirm}>Sí, ejecutar</button>
      </div>
    </Modal>
  );
}

export function SqlWorkspace({ conn, onTx, injected, theme }: {
  conn: Connection; onTx: (p: boolean) => void; injected: { sql: string; n: number } | null; theme: string;
}) {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [lineOffset, setLineOffset] = useState(0);
  const { run, running, response, error, pendingConfirm, setPendingConfirm } = useSqlRunner(conn.id, onTx);
  const runRef = useRef<(mode: "all" | "current") => void>(() => {});

  useEffect(() => {
    if (injected && editorRef.current) {
      const ed = editorRef.current;
      const model = ed.getModel()!;
      const last = model.getLineCount();
      const text = (model.getValueInRange(new monaco.Range(last, 1, last, model.getLineMaxColumn(last))).trim() ? "\n\n" : "\n") + injected.sql + "\n";
      ed.executeEdits("inject", [{ range: new monaco.Range(last, model.getLineMaxColumn(last), last, model.getLineMaxColumn(last)), text }]);
      const newLast = model.getLineCount();
      ed.revealLine(newLast);
      ed.setPosition({ lineNumber: newLast - 1, column: 1 });
      ed.focus();
    }
  }, [injected]);

  runRef.current = async (mode) => {
    const ed = editorRef.current;
    if (!ed) return;
    const model = ed.getModel()!;
    const selection = ed.getSelection();
    let sql = model.getValue();
    let offset = 0;
    if (mode === "all" && selection && !selection.isEmpty()) {
      sql = model.getValueInRange(selection);
      offset = selection.startLineNumber - 1;
    } else if (mode === "current") {
      const line = ed.getPosition()?.lineNumber ?? 1;
      const parts = await api.post<{ line: number; sql: string }[]>("/api/sql/analyze", { session_id: SESSION_ID, profile: conn.id, sql });
      const cur = [...parts].reverse().find((p) => p.line <= line) ?? parts[0];
      if (!cur) return;
      sql = cur.sql;
      offset = cur.line - 1;
    }
    setLineOffset(offset);
    save("editor", model.getValue());
    const res = await run(sql);
    markErrors(res, offset);
  };

  const markErrors = (res: ScriptResponse | null, offset: number) => {
    const model = editorRef.current?.getModel();
    if (!model) return;
    const markers: monaco.editor.IMarkerData[] = [];
    res?.results.forEach((r) => {
      if (r.error?.line) {
        const ln = r.error.line + offset;
        markers.push({ severity: monaco.MarkerSeverity.Error, message: r.error.message, startLineNumber: ln, endLineNumber: ln, startColumn: 1, endColumn: model.getLineMaxColumn(Math.min(ln, model.getLineCount())) });
      }
      r.compile_errors?.forEach((e) => {
        const ln = r.line + offset + e.line - 1;
        markers.push({ severity: monaco.MarkerSeverity.Error, message: e.text, startLineNumber: ln, endLineNumber: ln, startColumn: e.position, endColumn: e.position + 1 });
      });
    });
    monaco.editor.setModelMarkers(model, "oracle", markers);
  };

  const onMount: OnMount = (ed) => {
    editorRef.current = ed;
    registerOracleCompletion();
    ed.addAction({ id: "run-all", label: "Ejecutar script / selección", keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter], run: () => runRef.current("all") });
    ed.addAction({ id: "run-current", label: "Ejecutar sentencia actual", keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter], run: () => runRef.current("current") });
    ed.onDidChangeModelContent(() => save("editor", ed.getValue()));
  };

  const gotoLine = (line: number) => {
    const ln = line + lineOffset;
    editorRef.current?.revealLineInCenter(ln);
    editorRef.current?.setPosition({ lineNumber: ln, column: 1 });
    editorRef.current?.focus();
  };

  const tx = async (action: "commit" | "rollback") => {
    const r = await api.post<{ transaction_pending: boolean }>("/api/sql/transaction", { session_id: SESSION_ID, profile: conn.id, action });
    onTx(r.transaction_pending);
  };

  const history = showHistory ? store<HistoryItem[]>("history", []) : [];

  return (
    <div className="workspace">
      <div className="toolbar">
        <button className="primary" disabled={running} onClick={() => runRef.current("all")} title="Ctrl/⌘ + Enter">▶ Ejecutar</button>
        <button disabled={running} onClick={() => runRef.current("current")} title="Ctrl/⌘ + Shift + Enter">▷ Sentencia actual</button>
        <span className="sep" />
        <button disabled={!conn.writable} onClick={() => tx("commit")} title="Confirmar la transacción">✔ COMMIT</button>
        <button disabled={!conn.writable} onClick={() => tx("rollback")} title="Deshacer cambios no confirmados">↶ ROLLBACK</button>
        <span className="sep" />
        <button onClick={() => setShowHistory((s) => !s)} className={showHistory ? "active" : ""}>🕘 Historial</button>
        <div className="spacer" />
        {running && <span className="spinner" aria-label="Ejecutando" />}
        {!conn.writable && <span className="badge ro">SOLO LECTURA</span>}
      </div>
      {error && <div className="alert error">{error}</div>}
      <div className="split">
        <div className="editor-pane">
          <Editor
            defaultLanguage="sql"
            defaultValue={store<string>("editor", DEFAULT_SQL)}
            theme={theme === "dark" ? "vs-dark" : "vs"}
            onMount={onMount}
            options={{ minimap: { enabled: false }, fontSize: 14, automaticLayout: true, scrollBeyondLastLine: false, tabSize: 2, wordWrap: "on", quickSuggestions: true }}
          />
        </div>
        {showHistory && (
          <aside className="history">
            <div className="history-head">
              <b>Historial</b>
              <button className="link" onClick={() => { save("history", []); setShowHistory(false); }}>Vaciar</button>
            </div>
            {!history.length && <div className="muted pad">Aún no has ejecutado nada.</div>}
            {history.map((h, i) => (
              <button key={i} className={`history-item ${h.ok ? "" : "err"}`} onClick={() => {
                const ed = editorRef.current!;
                const m = ed.getModel()!;
                ed.executeEdits("history", [{ range: m.getFullModelRange(), text: h.sql }]);
                ed.focus();
              }} title="Cargar en el editor">
                <span className="muted">{new Date(h.at).toLocaleString()} · {h.profile} · {h.ms} ms</span>
                <code>{h.sql.slice(0, 160)}</code>
              </button>
            ))}
          </aside>
        )}
      </div>
      <ResultsPanel response={response} onGotoLine={gotoLine} />
      {pendingConfirm && (
        <DestructiveDialog
          info={pendingConfirm.info}
          onCancel={() => setPendingConfirm(null)}
          onConfirm={async () => {
            const sql = pendingConfirm.sql;
            setPendingConfirm(null);
            const res = await run(sql, true);
            markErrors(res, lineOffset);
          }}
        />
      )}
    </div>
  );
}
