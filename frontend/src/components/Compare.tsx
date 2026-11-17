import { useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import { api } from "../api";

interface Note { id?: string; title: string; note?: string; text?: string; count?: number }
interface Notes { general: Note[]; examples: { title: string; sql: string }[]; rules: Note[]; warnings: Note[] }
interface Translation { oracle_sql: string; applied: Note[]; warnings: Note[] }

export function Compare({ theme, onSendToEditor }: { theme: string; onSendToEditor: (sql: string) => void }) {
  const [notes, setNotes] = useState<Notes | null>(null);
  const [pg, setPg] = useState("");
  const [out, setOut] = useState<Translation | null>(null);

  useEffect(() => {
    api.get<Notes>("/api/compare/notes").then((n) => { setNotes(n); setPg(n.examples[0].sql); });
  }, []);

  useEffect(() => {
    if (!pg.trim()) { setOut(null); return; }
    const t = setTimeout(() => api.post<Translation>("/api/compare/translate", { sql: pg }).then(setOut), 300);
    return () => clearTimeout(t);
  }, [pg]);

  const opts = { minimap: { enabled: false }, fontSize: 13, automaticLayout: true, scrollBeyondLastLine: false, wordWrap: "on" as const };
  return (
    <div className="compare">
      <div className="toolbar">
        <b>Comparador PostgreSQL → Oracle</b>
        <span className="muted">Traducción aproximada basada en reglas: revisa siempre el resultado.</span>
        <div className="spacer" />
        <select onChange={(e) => e.target.value && setPg(notes!.examples[Number(e.target.value)].sql)} defaultValue="0" aria-label="Ejemplos">
          {notes?.examples.map((ex, i) => <option key={i} value={i}>Ejemplo: {ex.title}</option>)}
        </select>
      </div>
      <div className="compare-editors">
        <div>
          <div className="pane-title">PostgreSQL</div>
          <Editor language="sql" value={pg} onChange={(v) => setPg(v ?? "")} theme={theme === "dark" ? "vs-dark" : "vs"} options={opts} />
        </div>
        <div>
          <div className="pane-title">Oracle <button className="small" disabled={!out} onClick={() => out && onSendToEditor(out.oracle_sql)}>Abrir en el editor SQL ↗</button></div>
          <Editor language="sql" value={out?.oracle_sql ?? ""} theme={theme === "dark" ? "vs-dark" : "vs"} options={{ ...opts, readOnly: true }} />
        </div>
      </div>
      <div className="compare-notes">
        <div>
          <h4>Cambios aplicados</h4>
          {!out?.applied.length && <p className="muted">Ninguno.</p>}
          <ul>{out?.applied.map((a) => <li key={a.id}><b>{a.title}</b> {a.count! > 1 && `(×${a.count})`}<br /><span className="muted">{a.note}</span></li>)}</ul>
          {!!out?.warnings.length && (<>
            <h4>⚠ Requiere revisión manual</h4>
            <ul>{out.warnings.map((w) => <li key={w.id}><b>{w.title}</b><br /><span className="muted">{w.note}</span></li>)}</ul>
          </>)}
        </div>
        <div>
          <h4>Diferencias clave</h4>
          <dl>{notes?.general.map((n) => <div key={n.title}><dt>{n.title}</dt><dd>{n.text}</dd></div>)}</dl>
        </div>
      </div>
    </div>
  );
}
