# Uso del laboratorio

## Barra superior

- **Selector de conexión**: `Laboratorio local (LAB)` (borde verde, lectura/escritura) y, si lo configuraste,
  `Oracle remoto` (borde rojo, **solo lectura**). El perfil `SYSTEM` no aparece aquí a propósito.
- **Indicador** `● LAB@FREEPDB1`: verde si hay conexión; al pasar el ratón muestra la versión de Oracle.
- **Transacción pendiente**: aparece cuando hiciste DML sin `COMMIT`/`ROLLBACK`.
- **Restaurar estado inicial**: borra y recrea el esquema educativo (pide escribir `RESTAURAR`).
- ☀/☾: tema claro/oscuro.

## Editor SQL

| Atajo | Acción |
|---|---|
| `Ctrl/⌘ + Enter` | Ejecuta todo el script, o solo la **selección** si hay texto seleccionado |
| `Ctrl/⌘ + Shift + Enter` | Ejecuta la sentencia bajo el cursor |
| `Ctrl + Espacio` | Autocompletado (tablas, columnas, `alias.` → columnas, funciones, snippets `bloque`, `funcion`, `procedimiento`, `sel`) |

Reglas del script (iguales a SQL*Plus / SQL Developer):

- Las sentencias SQL terminan en `;`.
- Los bloques PL/SQL (`DECLARE`, `BEGIN`, `CREATE FUNCTION/PROCEDURE/PACKAGE/TRIGGER/TYPE`) terminan con una
  línea que contiene solo `/`.

Panel de resultados:

- Un botón por sentencia (✔ / ⚠ / ✖) con su línea; el primero con error se selecciona solo.
- **Datos**: hasta `MAX_ROWS` filas (500 por defecto). `(null)` en cursiva = NULL.
- **DBMS_OUTPUT**: lo que imprimas con `DBMS_OUTPUT.PUT_LINE` (se habilita automáticamente).
- **Mensajes**: filas afectadas, tiempos y texto de cada sentencia.
- Los errores Oracle muestran el código (`ORA-00942`, `PLS-00201`…), el mensaje y un enlace a la **línea**; el
  editor subraya la línea en rojo. Si creas una función/procedimiento con errores, se listan los de `USER_ERRORS`.

**Transacciones.** Cada pestaña del navegador es una sesión Oracle independiente. Prueba:

1. Pestaña A: `UPDATE pacientes SET ciudad = 'Lima' WHERE id_paciente = 1;`
2. Pestaña B: `SELECT ciudad FROM pacientes WHERE id_paciente = 1;` → aún ve el valor antiguo.
3. Pestaña A: `COMMIT;` → ahora B ve el cambio.

Recuerda que el DDL (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`) hace **COMMIT implícito**.

**Historial**: botón 🕘; guarda las últimas 100 ejecuciones en tu navegador. Clic para recargarlas.

## Explorador de objetos

Panel izquierdo: elige esquema, filtra por nombre y abre cualquier objeto.

- **Tablas/vistas**: *Estructura* (columnas, tipos, IDENTITY, NOT NULL, defaults, comentarios, PK/FK/UNIQUE/CHECK,
  índices, triggers, filas y estadísticas), *Datos* (paginados de 100 en 100, clic en cabecera para ordenar) y *DDL*.
- **Funciones/procedimientos/paquetes**: estado (VALID/INVALID), parámetros y código fuente.
- **Secuencias, índices, triggers**: propiedades del diccionario de datos.
- Botones *Consultar / Probar en editor* insertan una plantilla en el editor SQL.

## Diagrama ER

Generado desde `ALL_CONSTRAINTS`. 🔑 = PK, 🔗 = FK, `*` = NOT NULL. Arrastra, haz zoom y doble clic en el título de
una tabla para abrirla.

## Esquema educativo de citas médicas

| Tabla | Contenido (datos ficticios) |
|---|---|
| `ESPECIALIDADES` | 10 especialidades con tarifa base |
| `MEDICOS` | 25 médicos (2 inactivos), cada uno con usuario |
| `CONSULTORIOS` | 15 consultorios en 2 torres |
| `PACIENTES` | 300 pacientes (12 recién registrados sin citas) |
| `CITAS` | 1 500 citas entre hace 6 meses y dentro de 1 mes; estados PROGRAMADA, CONFIRMADA, ATENDIDA, CANCELADA, NO_ASISTIO |
| `HISTORIAS_CLINICAS` | una por cita atendida, con código CIE-10 |
| `PAGOS` | pagos de citas atendidas (PAGADO / PENDIENTE / REEMBOLSADO) |
| `USUARIOS`, `ROLES`, `USUARIO_ROLES` | 30 usuarios y 4 roles |
| `CITAS_AUDITORIA` | la llena el trigger `TRG_CITAS_AUDITORIA` al cambiar el estado de una cita |
| `LAB_METADATA` | marca del laboratorio (no la borres) |

Otros objetos: vistas `V_CITAS_DETALLE` y `V_INGRESOS_ESPECIALIDAD`; secuencia `SEQ_FACTURA`; funciones `FN_EDAD`
y `FN_TOTAL_PAGADO_PACIENTE`; procedimiento `PR_REGISTRAR_PAGO`; paquete `PKG_CITAS` (`agendar`, `cancelar`,
`medico_disponible`, `citas_del_dia`, `resumen_medico`); triggers `TRG_CITAS_BU` y `TRG_CITAS_AUDITORIA`.

Las fechas de las citas se generan **relativas al día en que se crea el esquema**, así siempre hay citas "de hoy" y
"de mañana". Restaurar regenera los datos idénticos (semilla fija) desplazados a la fecha actual.

## Ejercicios

15 ejercicios en 4 niveles. Cada uno trae explicación, tarea, pista, solución y validación automática:

- **Consultas** (`query`): tu última sentencia debe ser un `SELECT`; se compara su resultado con el de la solución
  (mismo número de columnas y mismos valores; el orden solo cuenta cuando el enunciado lo pide). Los nombres de
  columna no importan.
- **Comprobaciones** (`checks`): tras tu script se ejecutan consultas al diccionario y pruebas de comportamiento
  (por ejemplo, llamar a tu procedimiento y verificar que lanza `ORA-20010`). Se hacen dentro de un `SAVEPOINT`
  que se deshace al final, así que no alteran tu trabajo.

El progreso y tus borradores se guardan en el navegador. *Limpiar objetos* borra lo creado en los ejercicios de
DDL/PL-SQL para repetirlos.

## Comparador PostgreSQL → Oracle

Escribe SQL de PostgreSQL a la izquierda y verás la versión Oracle a la derecha, con la lista de reglas
aplicadas (LIMIT → FETCH FIRST, SERIAL → IDENTITY, `::` → CAST, ILIKE, NOW(), STRING_AGG → LISTAGG,
DATE_TRUNC → TRUNC, generate_series → CONNECT BY, EXCEPT → MINUS…) y avisos de lo que requiere revisión manual
(ON CONFLICT → MERGE, RETURNING, DISTINCT ON, cadenas vacías = NULL…). Es una ayuda didáctica, no un traductor
completo: revisa siempre el resultado. *Abrir en el editor SQL* lo lleva al editor para ejecutarlo.

## Administración

Vistas de solo lectura sobre la base **local**, consultadas como `SYSTEM`: instancia y base de datos, sesiones,
tablespaces, usuarios, segmentos, parámetros, top SQL y objetos bloqueados. *Ver SQL usado* muestra la consulta a
las vistas `V$`/`DBA_` para que aprendas a obtener esa información tú mismo.

Ejercicio sugerido: deja una transacción abierta en el editor (`UPDATE` sin `COMMIT`) y mira la sección
*Objetos bloqueados*.

## Protecciones

| Situación | Comportamiento |
|---|---|
| `DROP`, `TRUNCATE`, `PURGE`, `FLASHBACK` | Diálogo de confirmación que lista cada sentencia; nada se ejecuta hasta confirmar |
| `DELETE`/`UPDATE` sin `WHERE` | Igual |
| `ALTER … DROP`, PL/SQL con `DROP`/`TRUNCATE` | Igual |
| Conexión remota de solo lectura | Solo `SELECT`/`WITH`; el resto se bloquea antes de ejecutar y además se usa `SET TRANSACTION READ ONLY` |
| Restaurar | Exige escribir `RESTAURAR`; solo esquema del laboratorio; verifica el usuario; no borra esquemas sin `LAB_METADATA` |
| SQL como `SYSTEM` | No disponible desde el editor |
| Consultas largas | Se cancelan a los `QUERY_TIMEOUT_SECONDS` (60 s) |

## Pruebas automáticas

```bash
docker compose exec backend pytest -v
```

Las pruebas **restauran el esquema** al empezar y al terminar.

## API

La documentación interactiva de la API está en **http://localhost:8000/docs** (Swagger).
