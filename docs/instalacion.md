# Instalación

Requisitos comunes: **Git**, **Docker con Compose v2**, ~**6 GB de disco** y al menos **4 GB de RAM para
contenedores** (Oracle Free usa ~2–3 GB). No hace falta instalar Python, Node ni Oracle Instant Client en tu
máquina: todo corre en contenedores.

> **¿Por qué Oracle corre nativo en todas partes?** La imagen `gvenzl/oracle-free` (Oracle Database 23ai Free)
> publica builds **amd64** y **arm64**. Docker elige automáticamente la de tu CPU, así que en Apple Silicon no hay
> emulación Rosetta/QEMU. `./scripts/check-env.sh` lo comprueba consultando el manifiesto de la imagen **antes**
> de descargarla.

---

## 1. Ubuntu (ej. Dell Latitude 5401 · i7 9.ª gen · 14 GB · x86-64)

### 1.1 Instalar Docker Engine + Compose

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Usar Docker sin `sudo` (cierra sesión y vuelve a entrar después):

```bash
sudo usermod -aG docker "$USER"
```

### 1.2 Levantar el laboratorio

```bash
git clone <url-del-repositorio> oracle-dba-lab
cd oracle-dba-lab
cp .env.example .env
./scripts/check-env.sh
docker compose up -d --build
```

Con 14 GB de RAM no hay que ajustar nada. Si usas el portátil para otras tareas pesadas, Oracle Free se limita
solo a 2 GB de SGA+PGA.

---

## 2. Mac con Apple Silicon (M1, M2, M3, M4)

### Opción A — Docker Desktop (recomendada)

1. Instala [Docker Desktop para Mac con Apple Silicon](https://www.docker.com/products/docker-desktop/).
2. *Settings → Resources*: asigna **al menos 4 GB** de memoria (6 GB recomendado) y 2+ CPU.
3. No necesitas activar Rosetta: la imagen es arm64 nativa.

### Opción B — Colima (alternativa libre y ligera)

```bash
brew install colima docker docker-compose docker-buildx
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
ln -sfn "$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
colima start --cpu 4 --memory 6 --disk 40
```

Colima usa la arquitectura nativa (aarch64) por defecto. **No** uses `--arch x86_64`: forzaría emulación y Oracle
sería muy lento.

### Levantar

```bash
cp .env.example .env
./scripts/check-env.sh
docker compose up -d --build
```

---

## 3. Mac con procesador Intel

Igual que Apple Silicon (Docker Desktop para **Intel** o Colima); la imagen usada es la **amd64** nativa.
Asigna 4–6 GB de memoria a Docker/Colima.

---

## 4. Comprobar que todo funciona

```bash
docker compose ps                      # oracle debe aparecer "healthy"
curl -s localhost:8080/api/health      # {"status":"ok",...,"startup":{"seed":"creado"|"existente"}}
docker compose exec backend pytest -v  # 40 pruebas contra Oracle real
```

Abre **http://localhost:8080**. En la barra superior debe verse `● LAB@FREEPDB1` en verde.

Conexión desde otras herramientas (SQL Developer, DBeaver, SQLcl): `localhost:1521/FREEPDB1`, usuario `LAB`
(contraseña `LAB_DB_PASSWORD` de tu `.env`).

## 5. Operación diaria

| Acción | Comando |
|---|---|
| Detener (conserva datos) | `docker compose stop` |
| Arrancar de nuevo | `docker compose start` |
| Ver logs | `docker compose logs -f backend` |
| Actualizar tras cambios de código | `docker compose up -d --build` |
| **Borrar todo, incluidos los datos de Oracle** | `docker compose down -v` |

Los datos de Oracle viven en el volumen con nombre `oracle-dba-lab_oracle-data` (no en una ruta de tu disco).

---

## 6. Si Oracle no puede ejecutarse localmente: Oracle remoto

Si tu equipo no puede ejecutar la imagen (poca RAM, arquitectura sin soporte, políticas corporativas), el
script `check-env.sh` te lo indicará. Opciones:

1. **Esquema de práctica remoto** (lectura/escritura): pide a tu DBA un usuario **dedicado y vacío** (o crea uno
   en Oracle Cloud Free Tier / Autonomous Database con TLS sin wallet). En `.env`:

   ```ini
   LAB_DB_HOST=mi-servidor.ejemplo.com
   LAB_DB_PORT=1521
   LAB_DB_SERVICE=ORCLPDB1
   LAB_DB_USER=MI_USUARIO_PRACTICA
   LAB_DB_PASSWORD=********
   LAB_ALLOW_RESET=false      # actívalo solo si el esquema es exclusivamente tuyo
   ADMIN_ENABLED=false        # las vistas DBA requieren privilegios que no tendrás
   ```

   ```bash
   docker compose -f docker-compose.remote.yml up -d --build
   ```

   La app crea el esquema de citas médicas solo si el esquema está **vacío**, y la restauración se niega a borrar
   un esquema que no tenga la tabla marcadora `LAB_METADATA`.

2. **Base real de consulta** (solo lectura): configura `EXTERNAL_DB_DSN`, `EXTERNAL_DB_USER` y
   `EXTERNAL_DB_PASSWORD`. Aparecerá como un perfil más en el selector de conexión, marcado en rojo
   **REMOTO · SOLO LECTURA**. Solo se permiten `SELECT`/`WITH`; cualquier otra sentencia se bloquea antes de
   ejecutarse. `EXTERNAL_DB_ALLOW_WRITE=true` lo cambia, pero no se recomienda.

---

## 7. Desarrollo sin contenedores para backend/frontend (opcional)

Con Oracle levantado en Docker (`docker compose up -d oracle`):

```bash
# Backend (Python 3.11+)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
set -a && source ../.env && set +a
LAB_DB_HOST=localhost uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend (Node 20+)
cd frontend
npm install
npm run dev        # http://localhost:5173 (redirige /api a localhost:8000)
```

## 8. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `oracle` no llega a *healthy* | `docker compose logs oracle`. Revisa que Docker tenga ≥ 4 GB de RAM. |
| `ORA-01017: invalid username/password` | Cambiaste contraseñas en `.env` después del primer arranque. El usuario se crea solo con el volumen vacío: ejecuta `docker compose down -v` y vuelve a levantar. |
| Puerto 1521/8000/8080 ocupado | Cambia `ORACLE_PORT`, `BACKEND_PORT` o `FRONTEND_PORT` en `.env`. |
| `exec format error` | Docker está emulando otra arquitectura (p. ej. Colima con `--arch x86_64`). Recrea la VM con la arquitectura nativa. |
| Apple Silicon lento | Comprueba con `docker version` que el servidor es `arm64`. |
