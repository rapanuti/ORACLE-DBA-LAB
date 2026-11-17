import { useEffect, useState } from "react";
import type { ScriptResponse, StatementResult } from "../api";
import { DataGrid } from "./common";

const KIND_LABEL: Record<string, string> = {
  query: "Consulta", query_lock: "Consulta FOR UPDATE", dml: "DML", ddl: "DDL", plsql: "PL/SQL", tcl: "Transacción", other: "Sentencia",
};

function icon(r: StatementResult) {
  return r.status === "ok" ? "✔" : r.status === "warning" ? "⚠" : "✖";
}

export function ResultsPanel({ response, onGotoLine }: { response: ScriptResponse | null; onGotoLine?: (line: number) => void }) {
  const [sel, setSel] = useState(0);
  const [sub, setSub] = useState<"data" | "output" | "messages">("data");

  useEffect(() => {
    if (!response) return;
    const errIdx = response.results.findIndex((r) => r.status !== "ok");
    const lastQuery = [...response.results].map((r, i) => [r, i] as const).reverse().find(([r]) => r.rows)?.[1];
    const idx = errIdx >= 0 ? errIdx : lastQuery ?? response.results.length - 1;
    setSel(idx);
    const r = response.results[idx];
    setSub(r?.rows ? "data" : r?.dbms_output.length ? "output" : "messages");
  }, [response]);

  if (!response) return <div className="results empty muted">Ejecuta una sentencia con <kbd>Ctrl/⌘ + Enter</kbd> (todo el script o la selección) o <kbd>Ctrl/⌘ + Shift + Enter</kbd> (sentencia bajo el cursor).</div>;
  const r = response.results[sel];
  const output = response.results.flatMap((x) => x.dbms_output);

  return (
    <div className="results">
      <div className="results-summary">
        <span>{response.statements} sentencia(s) · {response.total_ms.toFixed(1)} ms total</span>
        {response.transaction_pending && <span className="badge warn">Transacción pendiente: usa COMMIT o ROLLBACK</span>}
      </div>
      {response.results.length > 1 && (
        <div className="stmt-list">
          {response.results.map((x, i) => (
            <button key={i} className={`stmt ${x.status} ${i === sel ? "active" : ""}`} onClick={() => setSel(i)} title={x.sql}>
              {icon(x)} L{x.line} · {x.keyword || KIND_LABEL[x.kind]}
            </button>
          ))}
        </div>
      )}
      {r && (
        <>
          <div className="result-head">
            <span className={`status ${r.status}`}>{icon(r)} {r.message}</span>
            <span className="muted">{KIND_LABEL[r.kind] ?? r.kind} · {r.elapsed_ms} ms</span>
            <div className="spacer" />
            <div className="subtabs">
              <button className={sub === "data" ? "active" : ""} onClick={() => setSub("data")} disabled={!r.rows}>Datos{r.rows ? ` (${r.rows.length}${r.truncated ? "+" : ""})` : ""}</button>
              <button className={sub === "output" ? "active" : ""} onClick={() => setSub("output")}>DBMS_OUTPUT{output.length ? ` (${output.length})` : ""}</button>
              <button className={sub === "messages" ? "active" : ""} onClick={() => setSub("messages")}>Mensajes</button>
            </div>
          </div>
          {r.error && (
            <div className="alert error ora">
              <b>{r.error.code}</b> {r.error.line && (
                <button className="link" onClick={() => onGotoLine?.(r.error!.line!)}>(línea {r.error.line})</button>
              )}
              <pre>{r.error.message}</pre>
            </div>
          )}
          {r.compile_errors && (
            <div className="alert warn">
              <b>Errores de compilación (USER_ERRORS)</b>
              <ul>{r.compile_errors.map((e, i) => <li key={i}>Línea {e.line}, col {e.position}: {e.text}</li>)}</ul>
            </div>
          )}
          <div className="result-body">
            {sub === "data" && r.rows && r.columns && <DataGrid columns={r.columns} rows={r.rows} />}
            {sub === "data" && !r.rows && <div className="muted pad">Esta sentencia no devuelve filas.</div>}
            {sub === "output" && (output.length ? <pre className="dbms">{output.join("\n")}</pre> : <div className="muted pad">Sin salida de DBMS_OUTPUT. Usa DBMS_OUTPUT.PUT_LINE('texto') en un bloque PL/SQL.</div>)}
            {sub === "messages" && (
              <div className="messages">
                {response.results.map((x, i) => (
                  <div key={i} className={`msg ${x.status}`}>
                    <span>{icon(x)} [línea {x.line}] {x.message}</span>
                    <span className="muted"> — {x.elapsed_ms} ms</span>
                    <pre>{x.sql.length > 300 ? x.sql.slice(0, 300) + "…" : x.sql}</pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
