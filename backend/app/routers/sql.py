from __future__ import annotations

import oracledb
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..db import get_profiles, sessions
from ..executor import PolicyError, error_payload, execute_script, transaction_pending
from ..sql_parser import classify, split_sql

router = APIRouter(prefix="/api", tags=["sql"])


class ExecuteRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    profile: str = "lab"
    sql: str = Field(min_length=1, max_length=500_000)
    confirm: bool = False
    stop_on_error: bool = True
    max_rows: int | None = Field(default=None, ge=1, le=10_000)


class TxRequest(BaseModel):
    session_id: str
    profile: str = "lab"
    action: str = Field(pattern="^(commit|rollback)$")


def get_session(session_id: str, profile: str):
    try:
        return sessions.get(session_id, profile)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except oracledb.Error as exc:
        raise HTTPException(503, {"message": "No se pudo conectar a Oracle", **error_payload(exc)})


@router.get("/connections")
def connections():
    sessions.reap_idle()
    return [
        {"id": p.id, "label": p.label, "kind": p.kind, "writable": p.writable,
         "dsn": p.dsn, "user": p.user.upper(), "editor": p.kind != "admin"}
        for p in get_profiles().values()
    ]


@router.post("/connections/{profile}/test")
def test_connection(profile: str):
    from ..db import pooled
    try:
        with pooled(profile, allow_admin=True) as conn:
            cur = conn.cursor()
            cur.execute("""SELECT SYS_CONTEXT('USERENV','CURRENT_USER'),
                                  SYS_CONTEXT('USERENV','CON_NAME'),
                                  SYS_CONTEXT('USERENV','SERVER_HOST'),
                                  (SELECT banner_full FROM v$version WHERE ROWNUM = 1)
                           FROM dual""")
            user, con, host, banner = cur.fetchone()
            return {"ok": True, "user": user, "container": con, "host": host,
                    "version": banner, "server_version": conn.version}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except oracledb.Error as exc:
        return JSONResponse(status_code=503, content={"ok": False, **error_payload(exc)})


@router.post("/sql/execute")
def execute(req: ExecuteRequest):
    sess = get_session(req.session_id, req.profile)
    try:
        res = execute_script(sess, req.sql, confirm=req.confirm,
                             stop_on_error=req.stop_on_error, max_rows=req.max_rows)
    except PolicyError as exc:
        return JSONResponse(status_code=exc.status, content=exc.payload)
    return res.as_dict()


@router.post("/sql/analyze")
def analyze(req: ExecuteRequest):
    """Divide y clasifica sin ejecutar (útil para depurar el divisor)."""
    out = []
    for s in split_sql(req.sql):
        c = classify(s.text)
        out.append({"line": s.start_line, "plsql": s.is_plsql, "kind": c.kind, "keyword": c.keyword,
                    "destructive": c.destructive, "reason": c.reason, "sql": s.text})
    return out


@router.post("/sql/transaction")
def transaction(req: TxRequest):
    sess = sessions.peek(req.session_id, req.profile)
    if sess is None:
        return {"transaction_pending": False, "message": "No hay sesión abierta"}
    with sess.lock:
        if req.action == "commit":
            sess.conn.commit()
            msg = "Commit completado"
        else:
            sess.conn.rollback()
            msg = "Rollback completado"
        return {"transaction_pending": transaction_pending(sess), "message": msg}


@router.get("/sql/session/{session_id}")
def session_state(session_id: str, profile: str = "lab"):
    sess = sessions.peek(session_id, profile)
    return {"open": sess is not None,
            "transaction_pending": transaction_pending(sess) if sess else False}


@router.delete("/sql/session/{session_id}")
def close_session(session_id: str):
    sessions.close(session_id)
    return {"closed": True}
