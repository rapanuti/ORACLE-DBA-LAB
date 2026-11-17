from __future__ import annotations

import oracledb
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import exercises as ex_mod
from .. import pg_compare
from ..config import get_settings
from ..db import sessions
from ..executor import PolicyError, error_payload
from ..seed.seeder import SeedError, reset_schema, schema_status
from .sql import get_session

router = APIRouter(prefix="/api", tags=["lab"])

RESET_PHRASE = "RESTAURAR"


class ResetRequest(BaseModel):
    confirm_text: str


@router.get("/lab/status")
def lab_status():
    try:
        st = schema_status()
    except (SeedError, oracledb.Error) as exc:
        raise HTTPException(503, str(exc))
    st["allow_reset"] = get_settings().lab_allow_reset
    st["reset_phrase"] = RESET_PHRASE
    return st


@router.post("/lab/reset")
def lab_reset(req: ResetRequest):
    if req.confirm_text.strip().upper() != RESET_PHRASE:
        raise HTTPException(400, f"Para confirmar escribe exactamente: {RESET_PHRASE}")
    # Cierra (rollback) todas las sesiones del laboratorio para liberar bloqueos.
    closed = sessions.close_profile("lab")
    try:
        result = reset_schema()
    except SeedError as exc:
        raise HTTPException(409, str(exc))
    except oracledb.Error as exc:
        raise HTTPException(500, error_payload(exc))
    result["sessions_closed"] = closed
    return result


# ------------------------------------------------------------ ejercicios
class RunExercise(BaseModel):
    session_id: str
    sql: str


@router.get("/exercises")
def list_exercises():
    return [ex_mod.public(e) for e in ex_mod.EXERCISES]


@router.get("/exercises/{ex_id}/solution")
def exercise_solution(ex_id: str):
    if ex_id not in ex_mod.BY_ID:
        raise HTTPException(404, "Ejercicio no encontrado")
    return {"solution": ex_mod.BY_ID[ex_id]["solution"]}


@router.post("/exercises/{ex_id}/run")
def run_exercise(ex_id: str, req: RunExercise):
    if ex_id not in ex_mod.BY_ID:
        raise HTTPException(404, "Ejercicio no encontrado")
    sess = get_session(req.session_id, "lab")  # los ejercicios SIEMPRE usan el esquema del laboratorio
    try:
        return ex_mod.run_exercise(sess, ex_id, req.sql)
    except PolicyError as exc:
        return JSONResponse(status_code=exc.status, content=exc.payload)


@router.post("/exercises/{ex_id}/cleanup")
def cleanup_exercise(ex_id: str, req: RunExercise):
    ex = ex_mod.BY_ID.get(ex_id)
    if not ex:
        raise HTTPException(404, "Ejercicio no encontrado")
    if not ex.get("cleanup"):
        return {"message": "Este ejercicio no necesita limpieza"}
    sess = get_session(req.session_id, "lab")
    with sess.lock:
        cur = sess.conn.cursor()
        cur.execute(ex["cleanup"])
        cur.close()
    return {"message": "Objetos del ejercicio eliminados; puedes intentarlo de nuevo"}


# ------------------------------------------------------------ comparador PG
class TranslateRequest(BaseModel):
    sql: str


@router.get("/compare/notes")
def compare_notes():
    return {"general": pg_compare.GENERAL_NOTES, "examples": pg_compare.EXAMPLES,
            "rules": [{"id": r[0], "title": r[1], "note": r[4]} for r in pg_compare.RULES],
            "warnings": [{"id": r[0], "title": r[1], "note": r[3]} for r in pg_compare.NOTES_ONLY]}


@router.post("/compare/translate")
def compare_translate(req: TranslateRequest):
    return pg_compare.translate(req.sql)
