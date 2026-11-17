"""Funciones administrativas (DBA) — SOLO LECTURA sobre la base LOCAL.

Usan el perfil "admin" (SYSTEM) y están separadas del editor SQL: el usuario no puede
ejecutar SQL arbitrario como SYSTEM desde la interfaz.
"""
from __future__ import annotations

import oracledb
from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..db import pooled
from ..executor import error_payload, to_json

router = APIRouter(prefix="/api/admin", tags=["admin"])

QUERIES = {
    "instance": """SELECT i.instance_name, i.host_name, i.version_full, i.status, i.database_status,
                          TO_CHAR(i.startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time,
                          ROUND((SYSDATE - i.startup_time) * 24, 1) AS uptime_horas,
                          d.name AS cdb, SYS_CONTEXT('USERENV','CON_NAME') AS pdb, d.log_mode, d.open_mode,
                          (SELECT value FROM v$parameter WHERE name = 'sga_target') AS sga_target,
                          (SELECT value FROM v$parameter WHERE name = 'pga_aggregate_target') AS pga_target
                   FROM v$instance i CROSS JOIN v$database d""",
    "sessions": """SELECT sid, serial#, username, status, osuser, machine, program, module, sql_id,
                          event, wait_class, seconds_in_wait,
                          TO_CHAR(logon_time, 'YYYY-MM-DD HH24:MI:SS') AS logon_time
                   FROM v$session WHERE type = 'USER' ORDER BY status, username""",
    "tablespaces": """SELECT t.tablespace_name, t.contents, t.status,
                             ROUND(m.used_space * t.block_size / 1024 / 1024, 1) AS usado_mb,
                             ROUND(m.tablespace_size * t.block_size / 1024 / 1024, 1) AS tamano_max_mb,
                             ROUND(m.used_percent, 2) AS pct_usado
                      FROM dba_tablespaces t
                      JOIN dba_tablespace_usage_metrics m ON m.tablespace_name = t.tablespace_name
                      ORDER BY t.tablespace_name""",
    "users": """SELECT username, account_status, default_tablespace, temporary_tablespace,
                       TO_CHAR(created, 'YYYY-MM-DD') AS created, profile,
                       TO_CHAR(last_login, 'YYYY-MM-DD HH24:MI') AS last_login
                FROM dba_users WHERE oracle_maintained = 'N' ORDER BY username""",
    "segments": """SELECT owner, segment_name, segment_type, ROUND(bytes / 1024 / 1024, 2) AS mb
                   FROM dba_segments WHERE owner IN (SELECT username FROM dba_users WHERE oracle_maintained = 'N')
                   ORDER BY bytes DESC FETCH FIRST 30 ROWS ONLY""",
    "parameters": """SELECT name, value, isdefault, ismodified, description
                     FROM v$parameter
                     WHERE name IN ('sga_target','pga_aggregate_target','processes','sessions','open_cursors',
                                    'db_block_size','undo_retention','compatible','optimizer_mode',
                                    'nls_language','nls_territory','nls_date_format','cpu_count',
                                    'memory_target','db_recovery_file_dest_size','audit_trail')
                     ORDER BY name""",
    "top_sql": """SELECT sql_id, parsing_schema_name AS esquema, executions,
                         ROUND(elapsed_time / 1000) AS elapsed_ms, ROUND(cpu_time / 1000) AS cpu_ms,
                         buffer_gets, disk_reads, SUBSTR(sql_text, 1, 200) AS sql_text
                  FROM v$sql
                  WHERE parsing_schema_name IN (SELECT username FROM dba_users WHERE oracle_maintained = 'N')
                  ORDER BY elapsed_time DESC FETCH FIRST 20 ROWS ONLY""",
    "locks": """SELECT s.sid, s.username, o.owner, o.object_name, o.object_type,
                       DECODE(l.locked_mode, 0,'None',1,'Null',2,'Row-S',3,'Row-X',4,'Share',5,'S/Row-X',6,'Exclusive') AS modo
                FROM v$locked_object l JOIN dba_objects o ON o.object_id = l.object_id
                JOIN v$session s ON s.sid = l.session_id""",
}

DESCRIPTIONS = {
    "instance": "Instancia y base de datos (V$INSTANCE, V$DATABASE)",
    "sessions": "Sesiones de usuario conectadas (V$SESSION)",
    "tablespaces": "Uso de tablespaces (DBA_TABLESPACE_USAGE_METRICS)",
    "users": "Usuarios/esquemas no mantenidos por Oracle (DBA_USERS)",
    "segments": "Segmentos más grandes (DBA_SEGMENTS)",
    "parameters": "Parámetros de inicialización relevantes (V$PARAMETER)",
    "top_sql": "SQL con más tiempo acumulado (V$SQL)",
    "locks": "Objetos bloqueados por transacciones abiertas (V$LOCKED_OBJECT)",
}


@router.get("")
def admin_index():
    s = get_settings()
    return {"enabled": s.admin_enabled, "user": s.admin_db_user.upper(),
            "sections": [{"id": k, "description": v, "sql": QUERIES[k]} for k, v in DESCRIPTIONS.items()]}


@router.get("/{section}")
def admin_section(section: str):
    if not get_settings().admin_enabled:
        raise HTTPException(403, "Las funciones administrativas están deshabilitadas (ADMIN_ENABLED=false)")
    sql = QUERIES.get(section)
    if not sql:
        raise HTTPException(404, "Sección desconocida")
    try:
        with pooled("admin", allow_admin=True) as conn:
            cur = conn.cursor()
            cur.execute(sql)
            cols = [d.name for d in cur.description]
            rows = [[to_json(v) for v in r] for r in cur.fetchall()]
            return {"section": section, "description": DESCRIPTIONS[section], "sql": sql,
                    "columns": cols, "rows": rows}
    except oracledb.Error as exc:
        raise HTTPException(502, error_payload(exc))
