"""Divide scripts SQL / PL/SQL en sentencias y las clasifica.

Reglas (compatibles con SQL*Plus / SQL Developer):
  * Sentencias SQL terminan en ';'.
  * Bloques PL/SQL (DECLARE, BEGIN, CREATE FUNCTION/PROCEDURE/PACKAGE/TRIGGER/TYPE)
    terminan con una línea que contiene solo '/', o al final del script.
  * Se respetan cadenas '...', q'[...]', identificadores "..." y comentarios.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PLSQL_START = re.compile(
    r"^(DECLARE|BEGIN|CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?"
    r"(FUNCTION|PROCEDURE|PACKAGE|TRIGGER|TYPE|LIBRARY)\b)",
    re.IGNORECASE,
)
PLSQL_OBJECT = re.compile(
    r"^CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?"
    r"(FUNCTION|PROCEDURE|PACKAGE\s+BODY|PACKAGE|TRIGGER|TYPE\s+BODY|TYPE)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?(\"[^\"]+\"|[\w$#]+)(?:\.(\"[^\"]+\"|[\w$#]+))?",
    re.IGNORECASE,
)

Q_CLOSERS = {"[": "]", "(": ")", "{": "}", "<": ">"}


@dataclass
class Statement:
    text: str
    start_line: int  # 1-based, línea del script donde empieza
    is_plsql: bool


def strip_leading_comments(sql: str) -> str:
    s = sql
    while True:
        s = s.lstrip()
        if s.startswith("--"):
            nl = s.find("\n")
            s = "" if nl < 0 else s[nl + 1 :]
        elif s.startswith("/*"):
            end = s.find("*/")
            s = "" if end < 0 else s[end + 2 :]
        else:
            return s


def _code_only(sql: str) -> str:
    """Devuelve el SQL sin cadenas ni comentarios (para heurísticas)."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "-" and sql.startswith("--", i):
            nl = sql.find("\n", i)
            i = n if nl < 0 else nl
            out.append(" ")
        elif c == "/" and sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
            out.append(" ")
        elif c in "qQ" and i + 2 < n and sql[i + 1] == "'":
            closer = Q_CLOSERS.get(sql[i + 2], sql[i + 2])
            end = sql.find(closer + "'", i + 3)
            i = n if end < 0 else end + 2
            out.append("''")
        elif c == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            i = j + 1
            out.append("''")
        elif c == '"':
            end = sql.find('"', i + 1)
            i = n if end < 0 else end + 1
            out.append('"X"')
        else:
            out.append(c)
            i += 1
    return "".join(out)


def split_sql(script: str) -> list[Statement]:
    statements: list[Statement] = []
    buf: list[str] = []
    buf_start_line = 1
    line = 1
    i, n = 0, len(script)
    at_line_start = True

    def flush(plsql_hint: bool | None = None) -> None:
        nonlocal buf, buf_start_line
        text = "".join(buf)
        buf = []
        start = buf_start_line
        buf_start_line = line
        code = strip_leading_comments(text).strip()
        if not code:
            return
        is_plsql = bool(PLSQL_START.match(code)) if plsql_hint is None else plsql_hint
        if not is_plsql:
            code = code.rstrip()
            while code.endswith(";"):
                code = code[:-1].rstrip()
        else:
            code = code.rstrip()
            if code.endswith("/"):
                code = code[:-1].rstrip()
        # línea real de inicio: saltar líneas vacías/comentarios iniciales
        lead = text[: len(text) - len(strip_leading_comments(text))]
        statements.append(Statement(code, start + lead.count("\n"), is_plsql))

    def current_is_plsql() -> bool:
        return bool(PLSQL_START.match(strip_leading_comments("".join(buf))))

    while i < n:
        c = script[i]
        if at_line_start:
            nl = script.find("\n", i)
            line_text = script[i : (n if nl < 0 else nl)]
            if line_text.strip() == "/":
                flush()
                i = n if nl < 0 else nl + 1
                line += 1
                buf_start_line = line
                continue
            at_line_start = False
        if c == "\n":
            buf.append(c)
            line += 1
            at_line_start = True
            i += 1
        elif c == "-" and script.startswith("--", i):
            nl = script.find("\n", i)
            end = n if nl < 0 else nl
            buf.append(script[i:end])
            i = end
        elif c == "/" and script.startswith("/*", i):
            end = script.find("*/", i + 2)
            end = n if end < 0 else end + 2
            chunk = script[i:end]
            buf.append(chunk)
            line += chunk.count("\n")
            i = end
        elif c in "qQ" and i + 2 < n and script[i + 1] == "'" and (i == 0 or not (script[i - 1].isalnum() or script[i - 1] == "_")):
            closer = Q_CLOSERS.get(script[i + 2], script[i + 2])
            end = script.find(closer + "'", i + 3)
            end = n if end < 0 else end + 2
            chunk = script[i:end]
            buf.append(chunk)
            line += chunk.count("\n")
            i = end
        elif c == "'":
            j = i + 1
            while j < n:
                if script[j] == "'":
                    if j + 1 < n and script[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            chunk = script[i : j + 1]
            buf.append(chunk)
            line += chunk.count("\n")
            i = j + 1
        elif c == '"':
            end = script.find('"', i + 1)
            end = n if end < 0 else end + 1
            buf.append(script[i:end])
            i = end
        elif c == ";":
            buf.append(c)
            i += 1
            if not current_is_plsql():
                flush(False)
        else:
            buf.append(c)
            i += 1
    flush()
    return statements


# ---------------------------------------------------------------- clasificación
QUERY_KW = {"SELECT", "WITH"}
DML_KW = {"INSERT", "UPDATE", "DELETE", "MERGE"}
TCL_KW = {"COMMIT", "ROLLBACK", "SAVEPOINT", "SET"}
DDL_KW = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "GRANT", "REVOKE",
          "COMMENT", "PURGE", "FLASHBACK", "ANALYZE", "AUDIT", "NOAUDIT"}
PLSQL_KW = {"BEGIN", "DECLARE", "CALL", "EXEC", "EXECUTE"}


@dataclass
class Classification:
    kind: str           # query | dml | ddl | plsql | tcl | other
    keyword: str
    destructive: bool
    reason: str = ""
    plsql_object: tuple[str, str] | None = None  # (TYPE, NAME) si crea objeto PL/SQL


def classify(stmt: str) -> Classification:
    code = _code_only(strip_leading_comments(stmt)).strip()
    m = re.match(r"[A-Za-z]+", code)
    kw = m.group(0).upper() if m else ""
    upper = re.sub(r"\s+", " ", code.upper())

    if kw in QUERY_KW:
        kind = "query"
    elif kw in DML_KW:
        kind = "dml"
    elif kw in TCL_KW:
        kind = "tcl"
    elif kw in DDL_KW:
        kind = "ddl"
    elif kw in PLSQL_KW:
        kind = "plsql"
    elif kw == "EXPLAIN":
        kind = "other"
    else:
        kind = "other"

    destructive, reason = False, ""
    if kw in {"DROP", "TRUNCATE", "PURGE", "FLASHBACK"}:
        destructive, reason = True, f"{kw} elimina objetos o datos de forma irreversible"
    elif kw in {"DELETE", "UPDATE"} and not re.search(r"\bWHERE\b", upper):
        destructive, reason = True, f"{kw} sin cláusula WHERE afecta a TODAS las filas"
    elif kw == "ALTER" and re.search(r"\bDROP\b", upper):
        destructive, reason = True, "ALTER ... DROP elimina columnas/restricciones"
    elif kind == "plsql" and re.search(r"\b(DROP|TRUNCATE)\b", upper):
        destructive, reason = True, "El bloque PL/SQL contiene DROP/TRUNCATE dinámico"

    plsql_obj = None
    om = PLSQL_OBJECT.match(strip_leading_comments(stmt).strip())
    if om:
        otype = re.sub(r"\s+", " ", om.group(1).upper())
        name = om.group(3) or om.group(2)
        name = name[1:-1] if name.startswith('"') else name.upper()
        plsql_obj = (otype, name)

    if kw == "SELECT" and re.search(r"\bFOR UPDATE\b", upper):
        kind = "query_lock"

    return Classification(kind, kw, destructive, reason, plsql_obj)
