"""Explorador de objetos basado en las vistas ALL_* del diccionario de datos."""
from __future__ import annotations

from typing import Any

import oracledb
from fastapi import APIRouter, HTTPException, Query

from ..db import get_profile, pooled
from ..executor import error_payload, to_json

router = APIRouter(prefix="/api/explorer", tags=["explorer"])

OBJECT_TYPES = ["TABLE", "VIEW", "INDEX", "SEQUENCE", "FUNCTION", "PROCEDURE", "PACKAGE", "TRIGGER", "TYPE", "SYNONYM"]
DDL_TYPES = {"TABLE": "TABLE", "VIEW": "VIEW", "INDEX": "INDEX", "SEQUENCE": "SEQUENCE",
             "FUNCTION": "FUNCTION", "PROCEDURE": "PROCEDURE", "PACKAGE": "PACKAGE",
             "TRIGGER": "TRIGGER", "TYPE": "TYPE", "SYNONYM": "SYNONYM"}


def _check_profile(profile: str) -> None:
    try:
        get_profile(profile)
    except (KeyError, PermissionError) as exc:
        raise HTTPException(400, str(exc))


def _rows(cur: oracledb.Cursor) -> list[dict[str, Any]]:
    cols = [d.name.lower() for d in cur.description]
    return [dict(zip(cols, (to_json(v) for v in r))) for r in cur.fetchall()]


def _run(profile: str, fn):
    _check_profile(profile)
    try:
        with pooled(profile) as conn:
            return fn(conn.cursor())
    except oracledb.Error as exc:
        raise HTTPException(502, error_payload(exc))


def _default_schema(cur) -> str:
    cur.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
    return cur.fetchone()[0]


def _assert_object(cur, owner: str, name: str, types: list[str]) -> str:
    binds = {"o": owner, "n": name}
    placeholders = ",".join(f":t{i}" for i in range(len(types)))
    binds.update({f"t{i}": t for i, t in enumerate(types)})
    cur.execute(f"SELECT object_type FROM all_objects WHERE owner = :o AND object_name = :n "
                f"AND object_type IN ({placeholders}) AND ROWNUM = 1", binds)
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, f"Objeto {owner}.{name} no encontrado o sin privilegios")
    return row[0]


def _q(ident: str) -> str:
    return '"' + ident.replace('"', '') + '"'


@router.get("/schemas")
def schemas(profile: str = "lab"):
    def fn(cur):
        current = _default_schema(cur)
        cur.execute("""SELECT u.username, (SELECT COUNT(*) FROM all_objects o WHERE o.owner = u.username) AS objetos
                       FROM all_users u WHERE u.oracle_maintained = 'N' ORDER BY u.username""")
        items = [{"name": r[0], "objects": r[1]} for r in cur.fetchall()]
        return {"current": current, "schemas": items}
    return _run(profile, fn)


@router.get("/objects")
def objects(profile: str = "lab", schema: str | None = None):
    def fn(cur):
        owner = schema or _default_schema(cur)
        cur.execute("""SELECT object_name, object_type, status, TO_CHAR(last_ddl_time, 'YYYY-MM-DD HH24:MI:SS')
                       FROM all_objects
                       WHERE owner = :o
                         AND object_type IN ('TABLE','VIEW','INDEX','SEQUENCE','FUNCTION','PROCEDURE',
                                             'PACKAGE','PACKAGE BODY','TRIGGER','TYPE','SYNONYM')
                         AND object_name NOT LIKE 'BIN$%' AND object_name NOT LIKE 'SYS_IL%'
                         AND object_name NOT LIKE 'SYS_LOB%' AND object_name NOT LIKE 'DR$%'
                       ORDER BY object_type, object_name""", o=owner)
        grouped: dict[str, list] = {t: [] for t in OBJECT_TYPES}
        body_status = {}
        for name, otype, status, ddl in cur.fetchall():
            if otype == "PACKAGE BODY":
                body_status[name] = status
                continue
            grouped.setdefault(otype, []).append({"name": name, "status": status, "last_ddl": ddl})
        for pkg in grouped.get("PACKAGE", []):
            if body_status.get(pkg["name"]) == "INVALID":
                pkg["status"] = "INVALID"
        return {"schema": owner, "groups": [{"type": t, "items": grouped[t]} for t in OBJECT_TYPES]}
    return _run(profile, fn)


@router.get("/table")
def table_detail(schema: str, name: str, profile: str = "lab"):
    def fn(cur):
        otype = _assert_object(cur, schema, name, ["TABLE", "VIEW"])
        cur.execute("""SELECT c.column_id, c.column_name, c.data_type, c.data_length, c.data_precision,
                              c.data_scale, c.nullable, c.data_default, c.identity_column, cc.comments
                       FROM all_tab_cols c
                       LEFT JOIN all_col_comments cc ON cc.owner = c.owner AND cc.table_name = c.table_name
                                                    AND cc.column_name = c.column_name
                       WHERE c.owner = :o AND c.table_name = :n AND c.hidden_column = 'NO'
                       ORDER BY c.column_id""", o=schema, n=name)
        columns = _rows(cur)
        for c in columns:
            c["type_display"] = _type_display(c)
            if isinstance(c.get("data_default"), str):
                c["data_default"] = c["data_default"].strip()
        cur.execute("""SELECT c.constraint_name, c.constraint_type, c.status, c.search_condition_vc,
                              c.delete_rule, r.owner AS r_owner, r.table_name AS r_table,
                              (SELECT LISTAGG(cc.column_name, ', ') WITHIN GROUP (ORDER BY cc.position)
                                 FROM all_cons_columns cc
                                WHERE cc.owner = c.owner AND cc.constraint_name = c.constraint_name) AS columns,
                              (SELECT LISTAGG(rc.column_name, ', ') WITHIN GROUP (ORDER BY rc.position)
                                 FROM all_cons_columns rc
                                WHERE rc.owner = r.owner AND rc.constraint_name = r.constraint_name) AS r_columns
                       FROM all_constraints c
                       LEFT JOIN all_constraints r ON r.owner = c.r_owner AND r.constraint_name = c.r_constraint_name
                       WHERE c.owner = :o AND c.table_name = :n
                       ORDER BY DECODE(c.constraint_type, 'P', 1, 'U', 2, 'R', 3, 4), c.constraint_name""",
                    o=schema, n=name)
        constraints = [c for c in _rows(cur)
                       if not (c["constraint_type"] == "C" and (c.get("search_condition_vc") or "").endswith("IS NOT NULL"))]
        cur.execute("""SELECT i.index_name, i.index_type, i.uniqueness, i.status,
                              LISTAGG(ic.column_name, ', ') WITHIN GROUP (ORDER BY ic.column_position) AS columns
                       FROM all_indexes i JOIN all_ind_columns ic
                         ON ic.index_owner = i.owner AND ic.index_name = i.index_name
                       WHERE i.table_owner = :o AND i.table_name = :n
                       GROUP BY i.index_name, i.index_type, i.uniqueness, i.status
                       ORDER BY i.index_name""", o=schema, n=name)
        indexes = _rows(cur)
        cur.execute("""SELECT trigger_name, trigger_type, triggering_event, status
                       FROM all_triggers WHERE table_owner = :o AND table_name = :n""", o=schema, n=name)
        triggers = _rows(cur)
        cur.execute("SELECT comments FROM all_tab_comments WHERE owner = :o AND table_name = :n", o=schema, n=name)
        comment = (cur.fetchone() or [None])[0]
        stats = {}
        if otype == "TABLE":
            cur.execute("""SELECT num_rows, blocks, TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI') AS last_analyzed
                           FROM all_tables WHERE owner = :o AND table_name = :n""", o=schema, n=name)
            stats = _rows(cur)[0]
        stats["row_count"] = None
        if profile == "lab" or (stats.get("num_rows") or 0) < 1_000_000:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {_q(schema)}.{_q(name)}")
                stats["row_count"] = cur.fetchone()[0]
            except oracledb.Error:
                pass
        return {"schema": schema, "name": name, "type": otype, "comment": comment, "columns": columns,
                "constraints": constraints, "indexes": indexes, "triggers": triggers, "stats": stats}
    return _run(profile, fn)


def _type_display(c: dict) -> str:
    t = c["data_type"]
    if t == "NUMBER":
        if c["data_precision"] is not None:
            return f"NUMBER({c['data_precision']}" + (f",{c['data_scale']})" if c["data_scale"] else ")")
        return "NUMBER"
    if t in ("VARCHAR2", "CHAR", "NVARCHAR2", "RAW"):
        return f"{t}({c['data_length']})"
    return t


@router.get("/table/data")
def table_data(schema: str, name: str, profile: str = "lab",
               offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
               order_by: str | None = None, desc: bool = False):
    def fn(cur):
        _assert_object(cur, schema, name, ["TABLE", "VIEW"])
        order = ""
        if order_by:
            cur.execute("SELECT COUNT(*) FROM all_tab_columns WHERE owner = :o AND table_name = :n AND column_name = :c",
                        o=schema, n=name, c=order_by)
            if cur.fetchone()[0] != 1:
                raise HTTPException(400, "Columna de ordenación inválida")
            order = f" ORDER BY {_q(order_by)} {'DESC' if desc else 'ASC'}"
        cur.execute(f"SELECT * FROM {_q(schema)}.{_q(name)}{order} OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY",
                    off=offset, lim=limit + 1)
        cols = [{"name": d.name, "type": d.type_code.name if d.type_code else ""} for d in cur.description]
        rows = [[to_json(v) for v in r] for r in cur.fetchall()]
        return {"columns": cols, "rows": rows[:limit], "offset": offset, "limit": limit,
                "has_more": len(rows) > limit}
    return _run(profile, fn)


@router.get("/ddl")
def ddl(schema: str, name: str, type: str, profile: str = "lab"):
    otype = type.upper()
    if otype not in DDL_TYPES:
        raise HTTPException(400, "Tipo de objeto no soportado")

    def fn(cur):
        _assert_object(cur, schema, name, [otype])
        try:
            cur.execute("""BEGIN
                             DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'STORAGE', FALSE);
                             DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SEGMENT_ATTRIBUTES', FALSE);
                             DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SQLTERMINATOR', TRUE);
                             DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PRETTY', TRUE);
                           END;""")
            cur.execute("SELECT DBMS_METADATA.GET_DDL(:t, :n, :o) FROM dual", t=DDL_TYPES[otype], n=name, o=schema)
            text = cur.fetchone()[0]
            source = "DBMS_METADATA"
        except oracledb.DatabaseError:
            cur.execute("""SELECT text FROM all_source WHERE owner = :o AND name = :n
                           AND type IN (:t, :t || ' BODY') ORDER BY type, line""", o=schema, n=name, t=otype)
            text = "".join(r[0] for r in cur.fetchall()) or "-- DDL no disponible (requiere privilegios)"
            source = "ALL_SOURCE"
        errors = []
        if otype in ("FUNCTION", "PROCEDURE", "PACKAGE", "TRIGGER", "TYPE", "VIEW"):
            cur.execute("""SELECT type, line, position, text FROM all_errors
                           WHERE owner = :o AND name = :n ORDER BY sequence""", o=schema, n=name)
            errors = _rows(cur)
        return {"ddl": (text or "").strip(), "source": source, "errors": errors}
    return _run(profile, fn)


@router.get("/object")
def object_info(schema: str, name: str, type: str, profile: str = "lab"):
    """Detalle de objetos no tabulares (secuencias, índices, PL/SQL, triggers)."""
    otype = type.upper()

    def fn(cur):
        _assert_object(cur, schema, name, [otype])
        info: dict[str, Any] = {}
        if otype == "SEQUENCE":
            cur.execute("""SELECT min_value, max_value, increment_by, cycle_flag, cache_size, last_number
                           FROM all_sequences WHERE sequence_owner = :o AND sequence_name = :n""", o=schema, n=name)
            info = _rows(cur)[0]
        elif otype == "INDEX":
            cur.execute("""SELECT i.table_name, i.index_type, i.uniqueness, i.status, i.blevel, i.distinct_keys,
                                  (SELECT LISTAGG(column_name, ', ') WITHIN GROUP (ORDER BY column_position)
                                     FROM all_ind_columns WHERE index_owner = i.owner AND index_name = i.index_name) AS columns
                           FROM all_indexes i WHERE i.owner = :o AND i.index_name = :n""", o=schema, n=name)
            info = _rows(cur)[0]
        elif otype == "TRIGGER":
            cur.execute("""SELECT table_name, trigger_type, triggering_event, status, when_clause
                           FROM all_triggers WHERE owner = :o AND trigger_name = :n""", o=schema, n=name)
            info = _rows(cur)[0]
        elif otype in ("FUNCTION", "PROCEDURE", "PACKAGE"):
            cur.execute("""SELECT object_name AS subprogram, procedure_name, overload
                           FROM all_procedures WHERE owner = :o AND object_name = :n
                           ORDER BY subprogram_id""", o=schema, n=name)
            info["subprograms"] = [r for r in _rows(cur) if r["procedure_name"] or otype != "PACKAGE"]
            cur.execute("""SELECT object_name AS subprogram_name, argument_name, position, data_type, in_out
                           FROM all_arguments WHERE owner = :o AND (package_name = :n OR (package_name IS NULL AND object_name = :n))
                           ORDER BY object_name, subprogram_id, position""", o=schema, n=name)
            info["arguments"] = _rows(cur)
        cur.execute("""SELECT status, TO_CHAR(created, 'YYYY-MM-DD HH24:MI:SS') AS created,
                              TO_CHAR(last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') AS last_ddl
                       FROM all_objects WHERE owner = :o AND object_name = :n AND object_type = :t""",
                    o=schema, n=name, t=otype)
        info["object"] = _rows(cur)[0]
        return info
    return _run(profile, fn)


@router.get("/erd")
def erd(profile: str = "lab", schema: str | None = None):
    def fn(cur):
        owner = schema or _default_schema(cur)
        cur.execute("""SELECT c.table_name, c.column_name, c.data_type, c.data_length, c.data_precision,
                              c.data_scale, c.nullable
                       FROM all_tab_columns c JOIN all_tables t ON t.owner = c.owner AND t.table_name = c.table_name
                       WHERE c.owner = :o ORDER BY c.table_name, c.column_id""", o=owner)
        tables: dict[str, dict] = {}
        for tname, col, dtype, dlen, prec, scale, nullable in cur.fetchall():
            t = tables.setdefault(tname, {"name": tname, "columns": []})
            t["columns"].append({"name": col, "type": _type_display({"data_type": dtype, "data_length": dlen,
                                                                     "data_precision": prec, "data_scale": scale}),
                                 "nullable": nullable == "Y", "pk": False, "fk": False})
        cur.execute("""SELECT c.table_name, cc.column_name, c.constraint_type, c.constraint_name,
                              r.table_name AS r_table, rc.column_name AS r_column
                       FROM all_constraints c
                       JOIN all_cons_columns cc ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name
                       LEFT JOIN all_constraints r ON r.owner = c.r_owner AND r.constraint_name = c.r_constraint_name
                       LEFT JOIN all_cons_columns rc ON rc.owner = r.owner AND rc.constraint_name = r.constraint_name
                                                    AND rc.position = cc.position
                       WHERE c.owner = :o AND c.constraint_type IN ('P','R')""", o=owner)
        rels: dict[str, dict] = {}
        for tname, col, ctype, cname, rtable, rcol in cur.fetchall():
            t = tables.get(tname)
            if not t:
                continue
            for c in t["columns"]:
                if c["name"] == col:
                    c["pk" if ctype == "P" else "fk"] = True
            if ctype == "R" and rtable in tables:
                rel = rels.setdefault(cname, {"name": cname, "from": tname, "to": rtable,
                                              "columns": [], "ref_columns": []})
                rel["columns"].append(col)
                rel["ref_columns"].append(rcol)
        return {"schema": owner, "tables": list(tables.values()), "relations": list(rels.values())}
    return _run(profile, fn)


@router.get("/completion")
def completion(profile: str = "lab", schema: str | None = None):
    def fn(cur):
        owner = schema or _default_schema(cur)
        cur.execute("""SELECT c.table_name, c.column_name, c.data_type
                       FROM all_tab_columns c WHERE c.owner = :o
                       ORDER BY c.table_name, c.column_id""", o=owner)
        tables: dict[str, list] = {}
        for t, c, d in cur.fetchall():
            tables.setdefault(t, []).append({"name": c, "type": d})
        cur.execute("""SELECT object_name, object_type FROM all_objects WHERE owner = :o
                       AND object_type IN ('FUNCTION','PROCEDURE','PACKAGE','SEQUENCE')""", o=owner)
        objects = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
        return {"schema": owner, "tables": tables, "objects": objects}
    return _run(profile, fn)
