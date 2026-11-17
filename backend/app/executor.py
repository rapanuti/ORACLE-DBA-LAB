"""Ejecución de scripts sobre una sesión, con políticas de seguridad."""
from __future__ import annotations

import base64
import datetime as dt
import decimal
import time
from dataclasses import dataclass
from typing import Any

import oracledb

from .config import get_settings
from .db import SqlSession
from .sql_parser import Classification, Statement, classify, split_sql

READ_ONLY_KINDS = {"query"}


class PolicyError(Exception):
    """La política de seguridad bloquea el script (no se ejecutó nada)."""

    def __init__(self, status: int, payload: dict[str, Any]):
        super().__init__(payload.get("message", "bloqueado"))
        self.status = status
        self.payload = payload


def to_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat(sep=" ") if isinstance(value, dt.datetime) else value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        b = bytes(value)
        return "0x" + b[:64].hex().upper() + ("…" if len(b) > 64 else "")
    if isinstance(value, oracledb.LOB):
        return to_json(value.read())
    return str(value)


def error_payload(exc: oracledb.Error, stmt: Statement | None = None) -> dict[str, Any]:
    err = exc.args[0] if exc.args else None
    code = getattr(err, "full_code", None) or "ERROR"
    message = getattr(err, "message", None) or str(exc)
    offset = getattr(err, "offset", 0) or 0
    line = None
    if stmt is not None:
        line = stmt.start_line + stmt.text[:offset].count("\n")
    return {"code": code, "message": message.strip(), "offset": offset, "line": line}


def plan_policy(session: SqlSession, statements: list[Statement], confirm: bool) -> list[Classification]:
    classes = [classify(s.text) for s in statements]
    if session.read_only:
        blocked = [
            {"index": i, "keyword": c.keyword, "line": s.start_line}
            for i, (s, c) in enumerate(zip(statements, classes))
            if c.kind not in READ_ONLY_KINDS
        ]
        if blocked:
            raise PolicyError(403, {
                "error": "read_only",
                "message": ("La conexión '" + session.profile.label + "' es de SOLO LECTURA. "
                            "Solo se permiten consultas SELECT/WITH. Se bloquearon "
                            f"{len(blocked)} sentencia(s) y no se ejecutó nada."),
                "blocked": blocked,
            })
    destructive = [
        {"index": i, "keyword": c.keyword, "reason": c.reason, "line": s.start_line,
         "preview": s.text[:160]}
        for i, (s, c) in enumerate(zip(statements, classes)) if c.destructive
    ]
    if destructive and not confirm:
        raise PolicyError(409, {
            "error": "confirmation_required",
            "message": "El script contiene operaciones destructivas. Confirma para ejecutarlo.",
            "statements": destructive,
            "profile": session.profile.label,
        })
    return classes


def read_dbms_output(cur: oracledb.Cursor, limit: int = 5000) -> list[str]:
    lines: list[str] = []
    line_var = cur.var(str, 32767)
    status_var = cur.var(int)
    while len(lines) < limit:
        cur.callproc("dbms_output.get_line", (line_var, status_var))
        if status_var.getvalue() != 0:
            break
        lines.append(line_var.getvalue() or "")
    return lines


def compile_errors(cur: oracledb.Cursor, obj: tuple[str, str]) -> list[dict[str, Any]]:
    otype, name = obj
    cur.execute(
        """SELECT line, position, text, attribute FROM user_errors
           WHERE name = :n AND type = :t ORDER BY sequence""",
        n=name, t=otype)
    return [{"line": r[0], "position": r[1], "text": r[2].strip(), "attribute": r[3]} for r in cur]


def run_statement(session: SqlSession, stmt: Statement, cls: Classification,
                  max_rows: int) -> dict[str, Any]:
    conn = session.conn
    cur = conn.cursor()
    cur.arraysize = min(max_rows + 1, 1000)
    result: dict[str, Any] = {
        "sql": stmt.text, "line": stmt.start_line, "kind": cls.kind, "keyword": cls.keyword,
        "status": "ok", "columns": None, "rows": None, "rowcount": None, "truncated": False,
        "elapsed_ms": 0.0, "dbms_output": [], "message": "", "error": None, "compile_errors": None,
    }
    if session.read_only:
        # Doble barrera: transacción de solo lectura en el servidor.
        conn.rollback()
        cur.execute("SET TRANSACTION READ ONLY")
    t0 = time.perf_counter()
    try:
        cur.execute(stmt.text)
        if cur.description:
            result["columns"] = [
                {"name": d.name, "type": d.type_code.name if d.type_code else "", "nullable": d.null_ok}
                for d in cur.description
            ]
            rows = cur.fetchmany(max_rows + 1)
            result["truncated"] = len(rows) > max_rows
            rows = rows[:max_rows]
            result["rows"] = [[to_json(v) for v in r] for r in rows]
            result["rowcount"] = len(rows)
            result["message"] = f"{len(rows)} fila(s) seleccionada(s)" + (
                f" (límite de {max_rows} alcanzado)" if result["truncated"] else "")
        else:
            result["rowcount"] = cur.rowcount
            result["message"] = _message_for(cls, cur.rowcount)
        result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        if cls.plsql_object and session.profile.kind != "external":
            errs = compile_errors(cur, cls.plsql_object)
            if errs:
                result["status"] = "warning"
                result["compile_errors"] = errs
                result["message"] = (f"{cls.plsql_object[0]} {cls.plsql_object[1]} creado con "
                                     f"{len(errs)} error(es) de compilación")
        elif getattr(cur, "warning", None):
            result["status"] = "warning"
            result["message"] += f" — Advertencia: {cur.warning}"
    except oracledb.Error as exc:
        result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        result["status"] = "error"
        result["error"] = error_payload(exc, stmt)
        result["message"] = result["error"]["message"]
    finally:
        try:
            result["dbms_output"] = read_dbms_output(cur)
        except oracledb.Error:
            pass
        cur.close()
    return result


def _message_for(cls: Classification, rowcount: int) -> str:
    kw = cls.keyword
    if cls.kind == "dml":
        verb = {"INSERT": "insertada(s)", "UPDATE": "actualizada(s)", "DELETE": "eliminada(s)",
                "MERGE": "fusionada(s)"}.get(kw, "afectada(s)")
        return f"{rowcount} fila(s) {verb}"
    if kw == "COMMIT":
        return "Commit completado"
    if kw == "ROLLBACK":
        return "Rollback completado"
    if cls.kind == "plsql":
        return "Procedimiento PL/SQL terminado correctamente"
    if cls.plsql_object:
        return f"{cls.plsql_object[0].capitalize()} {cls.plsql_object[1]} compilado"
    if cls.kind == "ddl":
        return f"{kw} ejecutado (DDL hace COMMIT implícito)"
    return "Sentencia ejecutada"


def transaction_pending(session: SqlSession) -> bool:
    try:
        return bool(session.conn.transaction_in_progress)
    except Exception:
        return False


@dataclass
class ScriptResult:
    results: list[dict[str, Any]]
    total_ms: float
    transaction_pending: bool

    def as_dict(self) -> dict[str, Any]:
        return {"results": self.results, "total_ms": self.total_ms,
                "transaction_pending": self.transaction_pending,
                "statements": len(self.results)}


def execute_script(session: SqlSession, script: str, *, confirm: bool = False,
                   stop_on_error: bool = True, max_rows: int | None = None) -> ScriptResult:
    max_rows = max_rows or get_settings().max_rows
    statements = split_sql(script)
    if not statements:
        raise PolicyError(400, {"error": "empty", "message": "No hay sentencias para ejecutar."})
    classes = plan_policy(session, statements, confirm)
    results = []
    t0 = time.perf_counter()
    with session.lock:
        for stmt, cls in zip(statements, classes):
            res = run_statement(session, stmt, cls, max_rows)
            results.append(res)
            if res["status"] == "error" and stop_on_error:
                break
        pending = transaction_pending(session)
    return ScriptResult(results, round((time.perf_counter() - t0) * 1000, 2), pending)
