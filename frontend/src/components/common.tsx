import { ReactNode, useEffect, useState } from "react";

export function fmt(v: unknown): string {
  if (v === null || v === undefined) return "";
  return typeof v === "object" ? JSON.stringify(v) : String(v);
}

export function DataGrid({ columns, rows, maxHeight, onSort, sort }: {
  columns: { name: string; type?: string }[]; rows: unknown[][]; maxHeight?: number | string;
  onSort?: (col: string) => void; sort?: { col: string; desc: boolean } | null;
}) {
  if (!columns.length) return <div className="muted pad">Sin columnas</div>;
  return (
    <div className="grid-wrap" style={{ maxHeight }}>
      <table className="grid">
        <thead>
          <tr>
            <th className="rownum">#</th>
            {columns.map((c) => (
              <th key={c.name} title={c.type} onClick={onSort ? () => onSort(c.name) : undefined} className={onSort ? "sortable" : ""}>
                {c.name}
                {sort?.col === c.name ? (sort.desc ? " ▼" : " ▲") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="rownum">{i + 1}</td>
              {r.map((v, j) => (
                <td key={j} className={v === null ? "null" : typeof v === "number" ? "num" : ""} title={fmt(v)}>
                  {v === null ? "(null)" : fmt(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <div className="muted pad">Sin filas</div>}
    </div>
  );
}

export function Modal({ title, children, onClose, tone = "default" }: {
  title: string; children: ReactNode; onClose: () => void; tone?: "default" | "danger";
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className={`modal ${tone}`} onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  );
}

/** Confirmación fuerte: hay que escribir una palabra para habilitar el botón. */
export function ConfirmDanger({ title, phrase, children, confirmLabel, onConfirm, onCancel, busy }: {
  title: string; phrase: string; children: ReactNode; confirmLabel: string;
  onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  const [text, setText] = useState("");
  return (
    <Modal title={title} onClose={onCancel} tone="danger">
      {children}
      <label className="confirm-label">
        <span>Escribe <b>{phrase}</b> para continuar:</span>
        <input autoFocus value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && text.trim().toUpperCase() === phrase && onConfirm()} />
      </label>
      <div className="modal-actions">
        <button onClick={onCancel}>Cancelar</button>
        <button className="danger" disabled={text.trim().toUpperCase() !== phrase || busy} onClick={onConfirm}>
          {busy ? "Procesando…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: {
  tabs: { id: T; label: ReactNode }[]; value: T; onChange: (v: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={t.id === value} className={t.id === value ? "active" : ""} onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return <div className="alert error">{msg}</div>;
}
