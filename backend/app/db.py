"""Perfiles de conexión, pools y sesiones de usuario (transacciones persistentes).

Perfiles:
  * lab       -> esquema educativo local. Lectura/escritura.
  * external  -> Oracle remoto opcional. SOLO LECTURA salvo EXTERNAL_DB_ALLOW_WRITE=true.
  * admin     -> SYSTEM en la base local, solo para /api/admin (vistas DBA/V$).
                 Nunca disponible en el editor SQL.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

import oracledb

from .config import get_settings

oracledb.defaults.fetch_lobs = False  # CLOB -> str, BLOB -> bytes


@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    kind: str
    writable: bool
    dsn: str
    user: str
    password: str = field(repr=False)


def get_profiles() -> dict[str, Profile]:
    s = get_settings()
    profiles = {
        "lab": Profile("lab", f"Laboratorio local ({s.lab_db_user.upper()})", "lab", True,
                       s.lab_dsn, s.lab_db_user, s.lab_db_password),
    }
    if s.external_configured:
        profiles["external"] = Profile(
            "external", f"Oracle remoto ({s.external_db_user.upper()}@{s.external_db_dsn})",
            "external", s.external_db_allow_write, s.external_db_dsn,
            s.external_db_user, s.external_db_password)
    if s.admin_enabled:
        profiles["admin"] = Profile("admin", f"Administración ({s.admin_db_user.upper()})",
                                    "admin", False, s.lab_dsn, s.admin_db_user, s.admin_password)
    return profiles


def get_profile(profile_id: str, *, allow_admin: bool = False) -> Profile:
    profiles = get_profiles()
    if profile_id not in profiles:
        raise KeyError(f"Perfil de conexión desconocido o no configurado: {profile_id}")
    if profile_id == "admin" and not allow_admin:
        raise PermissionError("El perfil administrativo no puede usarse desde el editor SQL.")
    return profiles[profile_id]


def connect(profile: Profile) -> oracledb.Connection:
    conn = oracledb.connect(user=profile.user, password=profile.password, dsn=profile.dsn)
    conn.call_timeout = get_settings().query_timeout_seconds * 1000
    conn.module = "oracle-dba-lab"
    return conn


# ------------------------------------------------------------------- pools
_pools: dict[str, oracledb.ConnectionPool] = {}
_pools_lock = threading.Lock()


def _pool(profile: Profile) -> oracledb.ConnectionPool:
    with _pools_lock:
        pool = _pools.get(profile.id)
        if pool is None:
            pool = oracledb.create_pool(user=profile.user, password=profile.password,
                                        dsn=profile.dsn, min=0, max=4, increment=1,
                                        ping_interval=30)
            _pools[profile.id] = pool
        return pool


@contextmanager
def pooled(profile_id: str, *, allow_admin: bool = False):
    """Conexión de servicio (explorador, admin). Siempre hace rollback al devolverla."""
    profile = get_profile(profile_id, allow_admin=allow_admin)
    conn = _pool(profile).acquire()
    conn.call_timeout = get_settings().query_timeout_seconds * 1000
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def close_pools() -> None:
    with _pools_lock:
        for p in _pools.values():
            try:
                p.close(force=True)
            except Exception:
                pass
        _pools.clear()


# ----------------------------------------------------------- sesiones SQL
class SqlSession:
    def __init__(self, session_id: str, profile: Profile):
        self.id = session_id
        self.profile = profile
        self.conn = connect(profile)
        self.lock = threading.Lock()
        self.last_used = time.time()
        cur = self.conn.cursor()
        cur.callproc("dbms_output.enable", [None])
        cur.close()

    @property
    def read_only(self) -> bool:
        return not self.profile.writable

    def close(self) -> None:
        try:
            self.conn.rollback()
            self.conn.close()
        except Exception:
            pass


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], SqlSession] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str, profile_id: str) -> SqlSession:
        profile = get_profile(profile_id)
        key = (session_id, profile_id)
        with self._lock:
            sess = self._sessions.get(key)
            if sess is not None:
                try:
                    sess.conn.ping()
                except Exception:
                    sess.close()
                    sess = None
            if sess is None:
                sess = SqlSession(session_id, profile)
                self._sessions[key] = sess
            sess.last_used = time.time()
            return sess

    def peek(self, session_id: str, profile_id: str) -> SqlSession | None:
        with self._lock:
            return self._sessions.get((session_id, profile_id))

    def close(self, session_id: str, profile_id: str | None = None) -> None:
        with self._lock:
            for key in [k for k in self._sessions if k[0] == session_id and (profile_id is None or k[1] == profile_id)]:
                self._sessions.pop(key).close()

    def close_profile(self, profile_id: str) -> int:
        with self._lock:
            keys = [k for k in self._sessions if k[1] == profile_id]
            for key in keys:
                self._sessions.pop(key).close()
            return len(keys)

    def reap_idle(self) -> None:
        limit = get_settings().session_idle_minutes * 60
        now = time.time()
        with self._lock:
            for key in [k for k, s in self._sessions.items() if now - s.last_used > limit and not s.lock.locked()]:
                self._sessions.pop(key).close()

    def close_all(self) -> None:
        with self._lock:
            for s in self._sessions.values():
                s.close()
            self._sessions.clear()


sessions = SessionManager()
