#!/usr/bin/env bash
# Verifica SO, arquitectura, Docker y compatibilidad de la imagen de Oracle
# ANTES de descargarla (usa "docker manifest inspect", que no descarga capas).
# Uso:  ./scripts/check-env.sh
set -u

cd "$(dirname "$0")/.."
IMAGE="$(grep -E '^ORACLE_IMAGE=' .env 2>/dev/null | cut -d= -f2-)"
IMAGE="${IMAGE:-gvenzl/oracle-free:23-slim-faststart}"

ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✖\033[0m %s\n' "$*"; }
STATUS=0

echo "== Sistema =="
OS="$(uname -s)"; ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) DARCH=amd64 ;;
  arm64|aarch64) DARCH=arm64 ;;
  *) DARCH="$ARCH" ;;
esac
if [ "$OS" = "Darwin" ]; then
  CPU="$(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
  MEM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
  ok "macOS $(sw_vers -productVersion 2>/dev/null) · $CPU · $ARCH · ${MEM_GB} GB RAM"
  [ "$DARCH" = "arm64" ] && ok "Apple Silicon: se usará la imagen arm64 nativa (sin emulación)."
  [ "$DARCH" = "amd64" ] && ok "Mac Intel: se usará la imagen amd64 nativa."
elif [ "$OS" = "Linux" ]; then
  CPU="$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs)"
  MEM_GB=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 / 1024 ))
  DISTRO="$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
  ok "$DISTRO · $CPU · $ARCH · ${MEM_GB} GB RAM"
else
  warn "Sistema $OS no probado (Windows: usa WSL2 + Docker Desktop)."
fi
if [ "${MEM_GB:-0}" -lt 8 ]; then warn "Menos de 8 GB de RAM: Oracle Free funcionará, pero cierra otras apps pesadas."; fi

echo "== Docker =="
if ! command -v docker >/dev/null 2>&1; then
  fail "Docker no está instalado."
  [ "$OS" = "Linux" ] && echo "     Ubuntu: https://docs.docker.com/engine/install/ubuntu/"
  [ "$OS" = "Darwin" ] && echo "     macOS: Docker Desktop (https://www.docker.com/products/docker-desktop/) o 'brew install colima docker docker-compose'"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  fail "El daemon de Docker no responde."
  [ "$OS" = "Darwin" ] && echo "     Abre Docker Desktop (open -a Docker) o ejecuta: colima start --cpu 4 --memory 6"
  [ "$OS" = "Linux" ] && echo "     sudo systemctl start docker   (y añade tu usuario al grupo docker)"
  exit 1
fi
ok "Docker $(docker version --format '{{.Server.Version}}') · servidor $(docker version --format '{{.Server.Arch}}')"
if docker compose version >/dev/null 2>&1; then ok "$(docker compose version)"; else fail "Falta 'docker compose' (plugin v2)."; STATUS=1; fi
DMEM=$(( $(docker info --format '{{.MemTotal}}') / 1024 / 1024 / 1024 ))
if [ "$DMEM" -lt 3 ]; then
  fail "Docker solo tiene ${DMEM} GB de RAM asignados; Oracle necesita ≥ 3 GB (recomendado 4+)."
  [ "$OS" = "Darwin" ] && echo "     Docker Desktop → Settings → Resources, o: colima start --memory 6"
  STATUS=1
else
  ok "Memoria disponible para contenedores: ${DMEM} GB"
fi
SARCH="$(docker version --format '{{.Server.Arch}}')"
if [ "$SARCH" != "$DARCH" ]; then
  warn "El servidor Docker es $SARCH pero la CPU es $DARCH (¿Colima con --arch distinto?). Habrá emulación lenta."
fi

echo "== Imagen de Oracle: $IMAGE =="
ARCHS="$(docker manifest inspect "$IMAGE" 2>/dev/null | grep -o '"architecture": *"[a-z0-9]*"' | cut -d'"' -f4 | sort -u | tr '\n' ' ')"
if [ -z "$ARCHS" ]; then
  warn "No se pudo consultar el manifiesto (¿sin Internet?). Se intentará igualmente al levantar."
elif echo " $ARCHS " | grep -q " $SARCH "; then
  ok "La imagen publica la arquitectura $SARCH (disponibles: $ARCHS) → Oracle se ejecutará de forma NATIVA."
else
  fail "La imagen NO tiene build para $SARCH (disponibles: $ARCHS)."
  echo "     Opciones: usa gvenzl/oracle-free (multi-arquitectura) o conecta a un Oracle remoto:"
  echo "     docker compose -f docker-compose.remote.yml up -d --build   (ver docs/instalacion.md)"
  STATUS=1
fi

echo "== Puertos =="
envval() { grep -E "^$1=" .env 2>/dev/null | cut -d= -f2-; }
ORACLE_PORT="$(envval ORACLE_PORT)"; BACKEND_PORT="$(envval BACKEND_PORT)"; FRONTEND_PORT="$(envval FRONTEND_PORT)"
for P in "${ORACLE_PORT:-1521}" "${BACKEND_PORT:-8000}" "${FRONTEND_PORT:-8080}"; do
  if (command -v lsof >/dev/null && lsof -iTCP:"$P" -sTCP:LISTEN -P >/dev/null 2>&1) ; then
    OWNER="$(docker ps --format '{{.Names}} {{.Ports}}' | grep -E ":$P->" | awk '{print $1}')"
    if echo "$OWNER" | grep -q oracle-dba-lab; then ok "Puerto $P en uso por Oracle DBA Lab"; else warn "Puerto $P ocupado ${OWNER:+por $OWNER}: cámbialo en .env"; fi
  else
    ok "Puerto $P libre"
  fi
done

[ -f .env ] && ok ".env presente" || warn "No existe .env: ejecuta  cp .env.example .env"
echo
[ $STATUS -eq 0 ] && echo "Todo listo:  docker compose up -d --build" || echo "Corrige los puntos marcados con ✖ antes de continuar."
exit $STATUS
