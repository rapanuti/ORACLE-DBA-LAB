from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

import oracledb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import close_pools, sessions
from .routers import admin, explorer, lab, sql
from .seed.seeder import ensure_seeded

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("oracle-dba-lab")

startup_state: dict = {"seed": "pendiente", "error": None}


def _auto_seed() -> None:
    """Espera a Oracle (hasta ~5 min) y crea el esquema educativo si está vacío."""
    for attempt in range(60):
        try:
            res = ensure_seeded()
            startup_state["seed"] = "creado" if res else "existente"
            startup_state["error"] = None
            log.info("Esquema educativo: %s %s", startup_state["seed"], res or "")
            return
        except oracledb.Error as exc:
            startup_state["error"] = str(exc)
            log.warning("Oracle aún no disponible (intento %s): %s", attempt + 1, exc)
            time.sleep(5)
        except Exception as exc:  # noqa: BLE001
            startup_state["seed"] = "error"
            startup_state["error"] = str(exc)
            log.exception("Error creando el esquema educativo")
            return
    startup_state["seed"] = "error"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().lab_auto_seed:
        threading.Thread(target=_auto_seed, daemon=True).start()
    else:
        startup_state["seed"] = "deshabilitado"
    yield
    sessions.close_all()
    close_pools()


app = FastAPI(title="Oracle DBA Lab API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(sql.router)
app.include_router(explorer.router)
app.include_router(lab.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "oracledb": oracledb.__version__, "thin_mode": oracledb.is_thin_mode(),
            "startup": startup_state}
