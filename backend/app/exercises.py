"""Ejercicios progresivos con validación automática.

Tipos de validación:
  * "query":  el script del alumno debe terminar en un SELECT; su resultado se compara
              con el de la solución (mismas columnas en número y mismos valores).
  * "checks": tras ejecutar el script del alumno se corren comprobaciones SQL/PL-SQL.
              Las comprobaciones se hacen dentro de un SAVEPOINT y se deshacen al final,
              para no alterar el trabajo del alumno.
"""
from __future__ import annotations

from typing import Any

import oracledb

from .db import SqlSession
from .executor import execute_script, error_payload, read_dbms_output, to_json
from .sql_parser import classify, split_sql

EXERCISES: list[dict[str, Any]] = [
    # ------------------------------------------------------------- Nivel 1
    {
        "id": "sel-01", "level": 1, "topic": "SELECT y ORDER BY",
        "title": "Pacientes de Valencia",
        "explanation": "La sentencia SELECT recupera filas. WHERE filtra y ORDER BY ordena. "
                       "En Oracle los literales de texto van entre comillas simples y son sensibles a mayúsculas.",
        "task": "Muestra documento, nombres y apellidos de los pacientes cuya ciudad es 'Valencia', "
                "ordenados por apellidos y luego por nombres.",
        "hint": "SELECT ... FROM pacientes WHERE ciudad = '...' ORDER BY apellidos, nombres",
        "starter": "SELECT documento, nombres, apellidos\nFROM pacientes\n-- completa aquí\n",
        "solution": "SELECT documento, nombres, apellidos FROM pacientes WHERE ciudad = 'Valencia' ORDER BY apellidos, nombres",
        "validation": {"type": "query", "ordered": True},
    },
    {
        "id": "sel-02", "level": 1, "topic": "Filtros con AND/IN",
        "title": "Médicos activos",
        "explanation": "Puedes combinar condiciones con AND / OR e IN. Las columnas CHAR(1) del esquema usan 'S'/'N'.",
        "task": "Lista nombres, apellidos y fecha_ingreso de los médicos ACTIVOS (activo = 'S'), "
                "del más antiguo al más reciente según fecha_ingreso.",
        "hint": "WHERE activo = 'S' ORDER BY fecha_ingreso",
        "starter": "SELECT nombres, apellidos, fecha_ingreso\nFROM medicos\n",
        "solution": "SELECT nombres, apellidos, fecha_ingreso FROM medicos WHERE activo = 'S' ORDER BY fecha_ingreso, id_medico",
        "validation": {"type": "query", "ordered": False},
    },
    {
        "id": "sel-03", "level": 1, "topic": "Funciones de fecha",
        "title": "Pacientes mayores de 65 años",
        "explanation": "MONTHS_BETWEEN(fecha1, fecha2) devuelve meses entre fechas; dividido entre 12 y truncado "
                       "con TRUNC da la edad. SYSDATE es la fecha/hora actual del servidor. "
                       "El esquema también trae la función FN_EDAD.",
        "task": "Muestra id_paciente, nombres y la edad (columna EDAD) de los pacientes con 65 años o más.",
        "hint": "TRUNC(MONTHS_BETWEEN(SYSDATE, fecha_nacimiento) / 12) AS edad",
        "starter": "SELECT id_paciente, nombres,\n       TRUNC(MONTHS_BETWEEN(SYSDATE, fecha_nacimiento) / 12) AS edad\nFROM pacientes\n",
        "solution": "SELECT id_paciente, nombres, fn_edad(fecha_nacimiento) AS edad FROM pacientes WHERE fn_edad(fecha_nacimiento) >= 65",
        "validation": {"type": "query", "ordered": False},
    },
    {
        "id": "sel-04", "level": 1, "topic": "FETCH FIRST (Top-N)",
        "title": "Las 3 especialidades más caras",
        "explanation": "Oracle 12c+ usa FETCH FIRST n ROWS ONLY (equivalente a LIMIT de PostgreSQL/MySQL). "
                       "Antes se usaba ROWNUM en una subconsulta ordenada.",
        "task": "Muestra nombre y tarifa_base de las 3 especialidades con mayor tarifa, de mayor a menor.",
        "hint": "ORDER BY tarifa_base DESC FETCH FIRST 3 ROWS ONLY",
        "starter": "SELECT nombre, tarifa_base\nFROM especialidades\n",
        "solution": "SELECT nombre, tarifa_base FROM especialidades ORDER BY tarifa_base DESC FETCH FIRST 3 ROWS ONLY",
        "validation": {"type": "query", "ordered": True},
    },
    # ------------------------------------------------------------- Nivel 2
    {
        "id": "join-01", "level": 2, "topic": "INNER JOIN",
        "title": "Agenda de mañana",
        "explanation": "JOIN combina filas de varias tablas según una condición (normalmente PK = FK). "
                       "TRUNC(SYSDATE) es hoy a medianoche; sumar 1 a una fecha suma un día.",
        "task": "Lista las citas de MAÑANA con: fecha_hora, nombre completo del paciente (columna PACIENTE = nombres || ' ' || apellidos), "
                "apellidos del médico (columna MEDICO) y estado. No uses la vista V_CITAS_DETALLE.",
        "hint": "JOIN pacientes p ON p.id_paciente = c.id_paciente JOIN medicos m ON ... WHERE c.fecha_hora >= TRUNC(SYSDATE) + 1 AND c.fecha_hora < TRUNC(SYSDATE) + 2",
        "starter": "SELECT c.fecha_hora,\n       p.nombres || ' ' || p.apellidos AS paciente,\n       m.apellidos AS medico,\n       c.estado\nFROM citas c\nJOIN pacientes p ON p.id_paciente = c.id_paciente\n-- une también con medicos y filtra por fecha\n",
        "solution": "SELECT c.fecha_hora, p.nombres || ' ' || p.apellidos AS paciente, m.apellidos AS medico, c.estado "
                    "FROM citas c JOIN pacientes p ON p.id_paciente = c.id_paciente JOIN medicos m ON m.id_medico = c.id_medico "
                    "WHERE c.fecha_hora >= TRUNC(SYSDATE) + 1 AND c.fecha_hora < TRUNC(SYSDATE) + 2",
        "validation": {"type": "query", "ordered": False},
    },
    {
        "id": "grp-01", "level": 2, "topic": "GROUP BY",
        "title": "Citas por estado",
        "explanation": "GROUP BY agrupa filas y permite funciones de agregación como COUNT, SUM, AVG, MIN, MAX.",
        "task": "Cuenta cuántas citas hay en cada estado. Columnas: ESTADO y TOTAL, ordenado por TOTAL descendente.",
        "hint": "SELECT estado, COUNT(*) AS total FROM citas GROUP BY estado ORDER BY total DESC",
        "starter": "SELECT estado, COUNT(*) AS total\nFROM citas\n",
        "solution": "SELECT estado, COUNT(*) AS total FROM citas GROUP BY estado ORDER BY total DESC",
        "validation": {"type": "query", "ordered": True},
    },
    {
        "id": "grp-02", "level": 2, "topic": "HAVING",
        "title": "Médicos con mucha actividad",
        "explanation": "HAVING filtra grupos después de agregar (WHERE filtra filas antes de agrupar).",
        "task": "Muestra id_medico y el número de citas ATENDIDAS (columna ATENDIDAS) de los médicos con más de 45 citas atendidas.",
        "hint": "WHERE estado = 'ATENDIDA' GROUP BY id_medico HAVING COUNT(*) > 45",
        "starter": "SELECT id_medico, COUNT(*) AS atendidas\nFROM citas\n",
        "solution": "SELECT id_medico, COUNT(*) AS atendidas FROM citas WHERE estado = 'ATENDIDA' GROUP BY id_medico HAVING COUNT(*) > 45",
        "validation": {"type": "query", "ordered": False},
    },
    {
        "id": "join-02", "level": 2, "topic": "LEFT JOIN / anti-join",
        "title": "Pacientes sin citas",
        "explanation": "LEFT JOIN conserva todas las filas de la tabla izquierda; si no hay coincidencia, las columnas "
                       "de la derecha quedan NULL. También puedes usar NOT EXISTS.",
        "task": "Lista id_paciente, nombres y apellidos de los pacientes que NUNCA han tenido una cita.",
        "hint": "LEFT JOIN citas c ON c.id_paciente = p.id_paciente WHERE c.id_cita IS NULL",
        "starter": "SELECT p.id_paciente, p.nombres, p.apellidos\nFROM pacientes p\n",
        "solution": "SELECT p.id_paciente, p.nombres, p.apellidos FROM pacientes p WHERE NOT EXISTS (SELECT 1 FROM citas c WHERE c.id_paciente = p.id_paciente)",
        "validation": {"type": "query", "ordered": False},
    },
    {
        "id": "grp-03", "level": 2, "topic": "JOIN + agregación",
        "title": "Ingresos por especialidad",
        "explanation": "Puedes agregar sobre varias tablas unidas. Ojo: solo cuentan los pagos en estado 'PAGADO'.",
        "task": "Calcula el total cobrado (estado PAGADO) por especialidad. Columnas: ESPECIALIDAD (nombre) y TOTAL. "
                "Ordena por TOTAL descendente.",
        "hint": "pagos -> citas -> medicos -> especialidades; SUM(pg.monto)",
        "starter": "SELECT e.nombre AS especialidad, SUM(pg.monto) AS total\nFROM pagos pg\n",
        "solution": "SELECT especialidad, total FROM v_ingresos_especialidad ORDER BY total DESC",
        "validation": {"type": "query", "ordered": True},
    },
    # ------------------------------------------------------------- Nivel 3
    {
        "id": "dml-01", "level": 3, "topic": "INSERT + COMMIT",
        "title": "Nueva especialidad",
        "explanation": "INSERT agrega filas. En Oracle las transacciones NO se confirman solas: los cambios solo "
                       "son visibles para otras sesiones tras COMMIT. La columna id_especialidad es IDENTITY, no la indiques.",
        "task": "Inserta la especialidad 'Medicina del Sueño' con descripción 'Trastornos del sueño' y tarifa_base 85. Luego haz COMMIT.",
        "hint": "INSERT INTO especialidades (nombre, descripcion, tarifa_base) VALUES (...); COMMIT;",
        "starter": "INSERT INTO especialidades (nombre, descripcion, tarifa_base)\nVALUES ( );\n\nCOMMIT;\n",
        "solution": "INSERT INTO especialidades (nombre, descripcion, tarifa_base) VALUES ('Medicina del Sueño', 'Trastornos del sueño', 85);\nCOMMIT;",
        "validation": {"type": "checks", "checks": [
            {"sql": "SELECT COUNT(*) FROM especialidades WHERE nombre = 'Medicina del Sueño' AND tarifa_base = 85",
             "expect": [[1]], "message": "Debe existir exactamente una especialidad 'Medicina del Sueño' con tarifa 85"},
            {"committed": True, "message": "La transacción debe estar confirmada (COMMIT)"},
        ]},
    },
    {
        "id": "dml-02", "level": 3, "topic": "UPDATE con WHERE + auditoría",
        "title": "Reprogramar por vacaciones",
        "explanation": "UPDATE modifica filas; siempre usa WHERE para limitar el alcance. El trigger TRG_CITAS_AUDITORIA "
                       "registra cada cambio de estado en CITAS_AUDITORIA.",
        "task": "El médico con id_medico = 3 se va de vacaciones: cambia a 'CANCELADA' todas sus citas en estado 'PROGRAMADA' "
                "o 'CONFIRMADA' con fecha futura (fecha_hora > SYSTIMESTAMP). Haz COMMIT.",
        "hint": "UPDATE citas SET estado = 'CANCELADA' WHERE id_medico = 3 AND estado IN (...) AND fecha_hora > SYSTIMESTAMP",
        "starter": "UPDATE citas\nSET estado = 'CANCELADA'\nWHERE id_medico = 3\n  -- completa las condiciones\n;\nCOMMIT;\n",
        "solution": "UPDATE citas SET estado = 'CANCELADA' WHERE id_medico = 3 AND estado IN ('PROGRAMADA','CONFIRMADA') AND fecha_hora > SYSTIMESTAMP;\nCOMMIT;",
        "validation": {"type": "checks", "checks": [
            {"sql": "SELECT COUNT(*) FROM citas WHERE id_medico = 3 AND estado IN ('PROGRAMADA','CONFIRMADA') AND fecha_hora > SYSTIMESTAMP",
             "expect": [[0]], "message": "No deben quedar citas futuras PROGRAMADAS/CONFIRMADAS del médico 3"},
            {"sql": "SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END FROM citas_auditoria a JOIN citas c ON c.id_cita = a.id_cita WHERE c.id_medico = 3 AND a.estado_nuevo = 'CANCELADA'",
             "expect": [[1]], "message": "El trigger de auditoría debe haber registrado las cancelaciones"},
            {"sql": "SELECT COUNT(*) FROM citas WHERE id_medico = 3 AND estado = 'ATENDIDA' AND fecha_actualizacion IS NOT NULL",
             "expect": [[0]], "message": "No debes modificar citas ya ATENDIDAS (revisa tu WHERE)"},
            {"committed": True, "message": "La transacción debe estar confirmada (COMMIT)"},
        ]},
    },
    {
        "id": "ddl-01", "level": 3, "topic": "CREATE TABLE + restricciones",
        "title": "Tabla de recordatorios",
        "explanation": "CREATE TABLE define columnas y restricciones: PRIMARY KEY, FOREIGN KEY, CHECK, DEFAULT. "
                       "En Oracle el DDL hace COMMIT implícito. GENERATED AS IDENTITY crea un autoincremental.",
        "task": "Crea la tabla RECORDATORIOS con: id_recordatorio (NUMBER IDENTITY, PK), id_cita (NUMBER NOT NULL, FK a CITAS), "
                "canal (VARCHAR2(10) con CHECK en 'SMS','EMAIL','WHATSAPP') y enviado (CHAR(1) DEFAULT 'N').",
        "hint": "CONSTRAINT fk_rec_cita FOREIGN KEY (id_cita) REFERENCES citas (id_cita)",
        "starter": "CREATE TABLE recordatorios (\n  id_recordatorio NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,\n  -- completa\n);\n",
        "solution": "CREATE TABLE recordatorios (\n  id_recordatorio NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,\n  id_cita NUMBER NOT NULL,\n  canal VARCHAR2(10) CHECK (canal IN ('SMS','EMAIL','WHATSAPP')),\n  enviado CHAR(1) DEFAULT 'N',\n  CONSTRAINT fk_rec_cita FOREIGN KEY (id_cita) REFERENCES citas (id_cita)\n);",
        "cleanup": "BEGIN EXECUTE IMMEDIATE 'DROP TABLE recordatorios CASCADE CONSTRAINTS PURGE'; EXCEPTION WHEN OTHERS THEN NULL; END;",
        "validation": {"type": "checks", "checks": [
            {"sql": "SELECT COUNT(*) FROM user_tab_columns WHERE table_name = 'RECORDATORIOS' AND column_name IN ('ID_RECORDATORIO','ID_CITA','CANAL','ENVIADO')",
             "expect": [[4]], "message": "La tabla RECORDATORIOS debe tener las 4 columnas pedidas"},
            {"sql": "SELECT COUNT(*) FROM user_constraints WHERE table_name = 'RECORDATORIOS' AND constraint_type = 'P'",
             "expect": [[1]], "message": "Falta la PRIMARY KEY"},
            {"sql": "SELECT COUNT(*) FROM user_constraints c JOIN user_constraints r ON r.constraint_name = c.r_constraint_name WHERE c.table_name = 'RECORDATORIOS' AND c.constraint_type = 'R' AND r.table_name = 'CITAS'",
             "expect": [[1]], "message": "Falta la FOREIGN KEY hacia CITAS"},
            {"sql": "SELECT identity_column FROM user_tab_columns WHERE table_name = 'RECORDATORIOS' AND column_name = 'ID_RECORDATORIO'",
             "expect": [["YES"]], "message": "id_recordatorio debe ser IDENTITY"},
            {"plsql": "INSERT INTO recordatorios (id_cita, canal) VALUES (1, 'FAX')", "expect_error": "ORA-02290",
             "message": "El CHECK debe rechazar canal = 'FAX'"},
            {"plsql": "INSERT INTO recordatorios (id_cita, canal) VALUES (1, 'SMS')",
             "message": "Debe poder insertarse un recordatorio válido"},
            {"sql": "SELECT enviado FROM recordatorios WHERE id_cita = 1 AND canal = 'SMS'",
             "expect": [["N"]], "message": "enviado debe tener DEFAULT 'N'"},
        ]},
    },
    # ------------------------------------------------------------- Nivel 4
    {
        "id": "plsql-01", "level": 4, "topic": "Bloque anónimo + DBMS_OUTPUT",
        "title": "Hola PL/SQL",
        "explanation": "Un bloque anónimo tiene DECLARE (opcional), BEGIN y END. SELECT ... INTO guarda un valor en una "
                       "variable. DBMS_OUTPUT.PUT_LINE imprime mensajes (el laboratorio los muestra en la pestaña DBMS_OUTPUT).",
        "task": "Escribe un bloque que cuente los pacientes y muestre con DBMS_OUTPUT el texto 'Total pacientes: N'.",
        "hint": "DECLARE v_total NUMBER; BEGIN SELECT COUNT(*) INTO v_total FROM pacientes; DBMS_OUTPUT.PUT_LINE('Total pacientes: ' || v_total); END;",
        "starter": "DECLARE\n  v_total NUMBER;\nBEGIN\n  -- cuenta y muestra\n  NULL;\nEND;\n/\n",
        "solution": "DECLARE\n  v_total NUMBER;\nBEGIN\n  SELECT COUNT(*) INTO v_total FROM pacientes;\n  DBMS_OUTPUT.PUT_LINE('Total pacientes: ' || v_total);\nEND;\n/",
        "validation": {"type": "checks", "checks": [
            {"output_equals_sql": "SELECT 'Total pacientes: ' || COUNT(*) FROM pacientes",
             "message": "DBMS_OUTPUT debe mostrar exactamente 'Total pacientes: N'"},
        ]},
    },
    {
        "id": "plsql-02", "level": 4, "topic": "Funciones PL/SQL",
        "title": "Función: citas de un paciente",
        "explanation": "CREATE OR REPLACE FUNCTION define una función almacenada que devuelve un valor con RETURN y puede "
                       "usarse dentro de SQL. Termina el bloque con una línea que contenga solo '/'.",
        "task": "Crea la función FN_CITAS_PACIENTE(p_id_paciente NUMBER) RETURN NUMBER que devuelva cuántas citas tiene el paciente. "
                "Pruébala con: SELECT fn_citas_paciente(1) FROM dual;",
        "hint": "SELECT COUNT(*) INTO v_n FROM citas WHERE id_paciente = p_id_paciente; RETURN v_n;",
        "starter": "CREATE OR REPLACE FUNCTION fn_citas_paciente (p_id_paciente IN NUMBER)\nRETURN NUMBER\nIS\n  v_n NUMBER;\nBEGIN\n  -- completa\n  RETURN v_n;\nEND;\n/\n\nSELECT fn_citas_paciente(1) FROM dual;\n",
        "solution": "CREATE OR REPLACE FUNCTION fn_citas_paciente (p_id_paciente IN NUMBER)\nRETURN NUMBER\nIS\n  v_n NUMBER;\nBEGIN\n  SELECT COUNT(*) INTO v_n FROM citas WHERE id_paciente = p_id_paciente;\n  RETURN v_n;\nEND;\n/\n\nSELECT fn_citas_paciente(1) FROM dual;",
        "cleanup": "BEGIN EXECUTE IMMEDIATE 'DROP FUNCTION fn_citas_paciente'; EXCEPTION WHEN OTHERS THEN NULL; END;",
        "validation": {"type": "checks", "checks": [
            {"sql": "SELECT status FROM user_objects WHERE object_name = 'FN_CITAS_PACIENTE' AND object_type = 'FUNCTION'",
             "expect": [["VALID"]], "message": "La función debe existir y compilar sin errores (VALID)"},
            {"sql": "SELECT COUNT(*) FROM pacientes WHERE fn_citas_paciente(id_paciente) <> (SELECT COUNT(*) FROM citas c WHERE c.id_paciente = pacientes.id_paciente)",
             "expect": [[0]], "message": "La función debe devolver el número correcto de citas para todos los pacientes"},
        ]},
    },
    {
        "id": "plsql-03", "level": 4, "topic": "Procedimientos y excepciones",
        "title": "Procedimiento: confirmar cita",
        "explanation": "Un procedimiento ejecuta lógica de negocio. RAISE_APPLICATION_ERROR(-20000..-20999, 'mensaje') "
                       "lanza errores propios. SQL%ROWCOUNT indica cuántas filas afectó el último DML.",
        "task": "Crea PR_CONFIRMAR_CITA(p_id_cita NUMBER) que cambie la cita a 'CONFIRMADA' solo si está 'PROGRAMADA'. "
                "Si no estaba PROGRAMADA (o no existe) debe lanzar RAISE_APPLICATION_ERROR(-20010, 'La cita no se puede confirmar'). "
                "No hagas COMMIT dentro del procedimiento.",
        "hint": "UPDATE citas SET estado = 'CONFIRMADA' WHERE id_cita = p_id_cita AND estado = 'PROGRAMADA'; IF SQL%ROWCOUNT = 0 THEN RAISE_APPLICATION_ERROR(...); END IF;",
        "starter": "CREATE OR REPLACE PROCEDURE pr_confirmar_cita (p_id_cita IN NUMBER)\nIS\nBEGIN\n  -- completa\n  NULL;\nEND;\n/\n",
        "solution": "CREATE OR REPLACE PROCEDURE pr_confirmar_cita (p_id_cita IN NUMBER)\nIS\nBEGIN\n  UPDATE citas SET estado = 'CONFIRMADA'\n   WHERE id_cita = p_id_cita AND estado = 'PROGRAMADA';\n  IF SQL%ROWCOUNT = 0 THEN\n    RAISE_APPLICATION_ERROR(-20010, 'La cita no se puede confirmar');\n  END IF;\nEND;\n/",
        "cleanup": "BEGIN EXECUTE IMMEDIATE 'DROP PROCEDURE pr_confirmar_cita'; EXCEPTION WHEN OTHERS THEN NULL; END;",
        "validation": {"type": "checks", "checks": [
            {"sql": "SELECT status FROM user_objects WHERE object_name = 'PR_CONFIRMAR_CITA' AND object_type = 'PROCEDURE'",
             "expect": [["VALID"]], "message": "El procedimiento debe existir y compilar (VALID)"},
            {"sql": "SELECT MIN(id_cita) FROM citas WHERE estado = 'PROGRAMADA'", "capture": "v",
             "message": "Se necesita al menos una cita PROGRAMADA (restaura el esquema si no hay)"},
            {"plsql": "BEGIN pr_confirmar_cita(:v); END;", "message": "Confirmar una cita PROGRAMADA no debe fallar"},
            {"sql": "SELECT estado FROM citas WHERE id_cita = :v", "expect": [["CONFIRMADA"]],
             "message": "La cita debe quedar CONFIRMADA"},
            {"plsql": "BEGIN pr_confirmar_cita(:v); END;", "expect_error": "ORA-20010",
             "message": "Confirmar una cita que ya no está PROGRAMADA debe lanzar ORA-20010"},
            {"plsql": "BEGIN pr_confirmar_cita(-1); END;", "expect_error": "ORA-20010",
             "message": "Una cita inexistente debe lanzar ORA-20010"},
        ]},
    },
]

BY_ID = {e["id"]: e for e in EXERCISES}


def public(ex: dict[str, Any], include_solution: bool = False) -> dict[str, Any]:
    keys = ["id", "level", "topic", "title", "explanation", "task", "hint", "starter"]
    out = {k: ex[k] for k in keys}
    out["validation_type"] = ex["validation"]["type"]
    out["has_cleanup"] = bool(ex.get("cleanup"))
    if include_solution:
        out["solution"] = ex["solution"]
    return out


def _norm(v: Any) -> Any:
    v = to_json(v)
    if isinstance(v, float):
        return round(v, 4) if v != int(v) else int(v)
    return v


def _fetch(cur: oracledb.Cursor, sql: str, binds: dict) -> list[list[Any]]:
    used = {k: v for k, v in binds.items() if f":{k}" in sql}
    cur.execute(sql, used)
    return [[_norm(x) for x in r] for r in cur.fetchall()] if cur.description else []


def _compare_query(session: SqlSession, ex: dict, user_sql: str, results: list[dict]) -> list[dict]:
    stmts = split_sql(user_sql)
    last = stmts[-1] if stmts else None
    if not last or classify(last.text).kind != "query":
        return [{"ok": False, "message": "Tu script debe terminar con una consulta SELECT."}]
    last_res = results[-1] if results else None
    if not last_res or last_res["status"] == "error":
        return [{"ok": False, "message": "La consulta produjo un error; corrígelo primero."}]
    cur = session.conn.cursor()
    try:
        expected = _fetch(cur, ex["solution"], {})
        cur.execute(last.text)
        got = [[_norm(x) for x in r] for r in cur.fetchall()]
    finally:
        cur.close()
    checks = []
    exp_cols = len(expected[0]) if expected else None
    got_cols = len(got[0]) if got else None
    if exp_cols is not None and got_cols is not None and exp_cols != got_cols:
        return [{"ok": False, "message": f"Se esperaban {exp_cols} columnas y tu consulta devuelve {got_cols}."}]
    checks.append({"ok": len(got) == len(expected),
                   "message": f"Número de filas: esperado {len(expected)}, obtenido {len(got)}"})
    if ex["validation"].get("ordered"):
        same = got == expected
        msg = "Mismos valores y en el mismo orden" if same else "Los valores o el orden no coinciden con lo esperado"
    else:
        key = lambda r: [(str(type(x)), str(x)) for x in r]  # noqa: E731
        same = sorted(got, key=key) == sorted(expected, key=key)
        msg = "Mismos valores (el orden no importa)" if same else "Los valores no coinciden con lo esperado"
    checks.append({"ok": same, "message": msg})
    return checks


def _run_checks(session: SqlSession, ex: dict, results: list[dict]) -> list[dict]:
    out: list[dict] = []
    binds: dict[str, Any] = {}
    conn = session.conn
    cur = conn.cursor()
    output = [line for r in results for line in r.get("dbms_output", [])]
    try:
        committed = not bool(getattr(conn, "transaction_in_progress", False))
        cur.execute("SAVEPOINT lab_validacion")
        for chk in ex["validation"]["checks"]:
            msg = chk["message"]
            try:
                if "committed" in chk:
                    out.append({"ok": committed, "message": msg})
                elif "output_equals_sql" in chk:
                    expected = _fetch(cur, chk["output_equals_sql"], binds)[0][0]
                    out.append({"ok": expected in [o.strip() for o in output],
                                "message": msg + f" (esperado: '{expected}')"})
                elif "plsql" in chk:
                    used = {k: v for k, v in binds.items() if f":{k}" in chk["plsql"]}
                    try:
                        cur.execute(chk["plsql"], used)
                        read_dbms_output(cur)
                        out.append({"ok": "expect_error" not in chk, "message": msg})
                    except oracledb.DatabaseError as exc:
                        code = error_payload(exc)["code"]
                        ok = chk.get("expect_error") == code
                        out.append({"ok": ok, "message": msg + ("" if ok else f" (error obtenido: {code})")})
                else:
                    rows = _fetch(cur, chk["sql"], binds)
                    if "capture" in chk:
                        val = rows[0][0] if rows else None
                        binds[chk["capture"]] = val
                        out.append({"ok": val is not None, "message": msg})
                    else:
                        ok = rows == chk["expect"]
                        out.append({"ok": ok, "message": msg + ("" if ok else f" (obtenido: {rows})")})
            except oracledb.DatabaseError as exc:
                e = error_payload(exc)
                out.append({"ok": False, "message": f"{msg} — {e['code']}: {e['message']}"})
    finally:
        try:
            cur.execute("ROLLBACK TO SAVEPOINT lab_validacion")
        except oracledb.DatabaseError:
            pass
        cur.close()
    return out


def run_exercise(session: SqlSession, ex_id: str, user_sql: str) -> dict[str, Any]:
    ex = BY_ID[ex_id]
    script = execute_script(session, user_sql, confirm=False, stop_on_error=True)
    results = script.results
    with session.lock:
        if any(r["status"] == "error" for r in results):
            checks = [{"ok": False, "message": "Tu script terminó con un error de Oracle. Revisa la pestaña de resultados."}]
        elif any(r["status"] == "warning" and r.get("compile_errors") for r in results):
            checks = [{"ok": False, "message": "Hay errores de compilación PL/SQL."}]
        elif ex["validation"]["type"] == "query":
            checks = _compare_query(session, ex, user_sql, results)
        else:
            checks = _run_checks(session, ex, results)
        pending = bool(getattr(session.conn, "transaction_in_progress", False))
    passed = all(c["ok"] for c in checks)
    return {"exercise_id": ex_id, "passed": passed, "checks": checks,
            **script.as_dict(), "transaction_pending": pending}
