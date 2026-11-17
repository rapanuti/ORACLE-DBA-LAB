/* Monaco empaquetado localmente (sin CDN) + autocompletado Oracle. */
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import "monaco-editor/esm/vs/editor/editor.all";
import "monaco-editor/esm/vs/basic-languages/sql/sql.contribution";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { loader } from "@monaco-editor/react";
import { api } from "./api";

(self as any).MonacoEnvironment = { getWorker: () => new EditorWorker() };
loader.config({ monaco });

const KEYWORDS = `SELECT FROM WHERE AND OR NOT IN EXISTS BETWEEN LIKE IS NULL ORDER BY GROUP HAVING DISTINCT AS
JOIN INNER LEFT RIGHT FULL OUTER CROSS ON USING UNION ALL MINUS INTERSECT INSERT INTO VALUES UPDATE SET DELETE MERGE
MATCHED WHEN THEN ELSE END CASE COMMIT ROLLBACK SAVEPOINT CREATE OR REPLACE TABLE VIEW INDEX SEQUENCE FUNCTION PROCEDURE
PACKAGE BODY TRIGGER BEFORE AFTER FOR EACH ROW DECLARE BEGIN EXCEPTION RETURN RETURNING IS LOOP WHILE IF ELSIF
CONSTRAINT PRIMARY KEY FOREIGN REFERENCES UNIQUE CHECK DEFAULT GENERATED IDENTITY ALTER ADD MODIFY DROP TRUNCATE
GRANT REVOKE FETCH FIRST NEXT ROWS ONLY OFFSET WITH CONNECT PRIOR START LEVEL ROWNUM ROWID DUAL ASC DESC NULLS LAST
VARCHAR2 NUMBER DATE TIMESTAMP CLOB BLOB CHAR INTEGER BOOLEAN PARTITION OVER`.split(/\s+/);
const FUNCTIONS = `COUNT SUM AVG MIN MAX NVL NVL2 COALESCE DECODE TO_CHAR TO_DATE TO_NUMBER TRUNC ROUND SYSDATE SYSTIMESTAMP
MONTHS_BETWEEN ADD_MONTHS LAST_DAY EXTRACT UPPER LOWER INITCAP SUBSTR INSTR LENGTH REPLACE TRIM LPAD RPAD CONCAT
LISTAGG ROW_NUMBER RANK DENSE_RANK LAG LEAD REGEXP_LIKE REGEXP_SUBSTR REGEXP_REPLACE CAST ABS MOD POWER SQRT
DBMS_OUTPUT.PUT_LINE RAISE_APPLICATION_ERROR`.split(/\s+/);

const SNIPPETS: Array<[string, string, string]> = [
  ["bloque", "Bloque anónimo PL/SQL", "DECLARE\n  ${1:v_total} NUMBER;\nBEGIN\n  ${2:NULL};\n  DBMS_OUTPUT.PUT_LINE(${3:'Hola'});\nEND;\n/"],
  ["funcion", "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION ${1:fn_nombre} (p_id IN NUMBER) RETURN NUMBER IS\n  v_res NUMBER;\nBEGIN\n  ${2:SELECT COUNT(*) INTO v_res FROM dual};\n  RETURN v_res;\nEND;\n/"],
  ["procedimiento", "CREATE PROCEDURE", "CREATE OR REPLACE PROCEDURE ${1:pr_nombre} (p_id IN NUMBER) IS\nBEGIN\n  ${2:NULL};\nEND;\n/"],
  ["sel", "SELECT ... FROM", "SELECT ${1:*}\nFROM ${2:tabla}\nWHERE ${3:1 = 1}\nFETCH FIRST ${4:50} ROWS ONLY;"],
];

let catalog: { tables: Record<string, { name: string; type: string }[]>; objects: { name: string; type: string }[] } = { tables: {}, objects: [] };
let registered = false;

export async function refreshCompletion(profile: string, schema?: string) {
  try {
    catalog = await api.get("/api/explorer/completion", { profile, schema });
  } catch { /* sin catálogo */ }
}

function aliasMap(text: string): Record<string, string> {
  const map: Record<string, string> = {};
  const re = /\b(?:FROM|JOIN)\s+(?:\w+\.)?("?[\w$#]+"?)(?:\s+(?:AS\s+)?([a-zA-Z_]\w*))?/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const table = m[1].replace(/"/g, "").toUpperCase();
    map[table] = table;
    if (m[2] && !KEYWORDS.includes(m[2].toUpperCase())) map[m[2].toUpperCase()] = table;
  }
  return map;
}

export function registerOracleCompletion() {
  if (registered) return;
  registered = true;
  monaco.languages.registerCompletionItemProvider("sql", {
    triggerCharacters: [".", " "],
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position);
      const range = new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn);
      const before = model.getValueInRange(new monaco.Range(position.lineNumber, 1, position.lineNumber, word.startColumn));
      const K = monaco.languages.CompletionItemKind;
      const dot = before.match(/([\w$#]+)\.$/);
      if (dot) {
        const table = aliasMap(model.getValue())[dot[1].toUpperCase()] ?? dot[1].toUpperCase();
        const cols = catalog.tables[table] ?? [];
        return { suggestions: cols.map((c) => ({ label: c.name.toLowerCase(), detail: c.type, kind: K.Field, insertText: c.name.toLowerCase(), range })) };
      }
      const inScope = Object.values(aliasMap(model.getValue()));
      const suggestions: monaco.languages.CompletionItem[] = [
        ...KEYWORDS.map((k) => ({ label: k, kind: K.Keyword, insertText: k, range })),
        ...FUNCTIONS.map((f) => ({ label: f, kind: K.Function, insertText: f, range })),
        ...Object.keys(catalog.tables).map((t) => ({ label: t.toLowerCase(), detail: "tabla/vista", kind: K.Class, insertText: t.toLowerCase(), range })),
        ...catalog.objects.map((o) => ({ label: o.name.toLowerCase(), detail: o.type.toLowerCase(), kind: o.type === "SEQUENCE" ? K.Constant : K.Method, insertText: o.name.toLowerCase(), range })),
        ...inScope.flatMap((t) => (catalog.tables[t] ?? []).map((c) => ({ label: c.name.toLowerCase(), detail: `${t}.${c.type}`, kind: K.Field, insertText: c.name.toLowerCase(), range, sortText: "0" }))),
        ...SNIPPETS.map(([label, detail, body]) => ({ label, detail, kind: K.Snippet, insertText: body, insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range })),
      ];
      return { suggestions };
    },
  });
}

export { monaco };
