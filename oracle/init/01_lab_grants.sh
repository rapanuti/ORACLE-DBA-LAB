#!/bin/bash
# Se ejecuta UNA vez, cuando el volumen de datos está vacío (primer arranque).
# El usuario ${APP_USER} ya fue creado por la imagen en FREEPDB1.
set -e
echo "[oracle-dba-lab] Otorgando privilegios adicionales a ${APP_USER}..."
sqlplus -s / as sysdba <<EOF
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;
GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE SEQUENCE,
      CREATE PROCEDURE, CREATE TRIGGER, CREATE TYPE, CREATE SYNONYM,
      CREATE MATERIALIZED VIEW TO ${APP_USER};
ALTER USER ${APP_USER} QUOTA UNLIMITED ON USERS;
EXIT
EOF
echo "[oracle-dba-lab] Privilegios otorgados."
