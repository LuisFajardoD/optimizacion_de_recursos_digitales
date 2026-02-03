# Optimización de Recursos Digitales — Plataforma Web (Proyecto VIII)

Plataforma web (MVP) para **optimizar imágenes por lote** mediante un flujo de **jobs** (trabajos).

Componentes:
- **Frontend**: React + Vite + TypeScript
- **Backend**: Django + Django REST Framework
- **Worker local**: procesamiento en segundo plano (jobs)

**Alcance actual:** optimización de imágenes (video queda como fase posterior).

---

## Contenido

- [Objetivo](#objetivo)
- [Tecnologías](#tecnologías)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Flujo general](#flujo-general)
- [Requisitos](#requisitos)
- [Ejecución en local](#ejecución-en-local)
  - [Backend (API)](#backend-api)
  - [Worker](#worker)
  - [Frontend (UI)](#frontend-ui)
- [Variables de entorno](#variables-de-entorno)
- [API (endpoints)](#api-endpoints)
- [Almacenamiento local](#almacenamiento-local)
- [Límites y formatos](#límites-y-formatos)
- [Funcionalidades del MVP](#funcionalidades-del-mvp)
- [Backlog (priorizado)](#backlog-priorizado)

---

## Objetivo

Optimizar imágenes por lote para reducir peso y estandarizar resultados:

- Subida de varias imágenes
- Procesamiento en segundo plano
- Ajustes por archivo (cuando aplique)
- Descarga final en **ZIP** con resultados y reportes

---

## Tecnologías

- Frontend: React + Vite + TypeScript
- Backend: Django + Django REST Framework
- Procesamiento: Worker local (comando Django)

---

## Estructura del repositorio

- `frontend/` — interfaz web
- `backend/` — API, modelos, presets, settings, lógica de optimización
- `docs/` — documentación adicional (si se mantiene)

---

## Flujo general

1) La UI envía `multipart/form-data` a `POST /api/jobs/` con `preset` y `files[]`.
2) El backend valida límites, crea:
   - `Job` (trabajo)
   - `JobFile` (archivo dentro del trabajo)
3) El job queda en `PENDING`.
4) El worker procesa jobs `PENDING` → `RUNNING` → `DONE` (o `FAILED`).
5) Se genera un **ZIP** por job con:
   - imágenes optimizadas
   - `reporte.txt`
   - `reporte.csv`
6) La UI consulta estado y permite descargar el ZIP.

---

## Requisitos

- Node.js 18+
- Python 3.9+

Puertos por defecto:
- Frontend: `http://127.0.0.1:5173`
- Backend: `http://localhost:8000`
- API base: `http://localhost:8000/api/`

---

## Ejecución en local

### Backend (API)

1) Crear entorno virtual (una sola vez):

```powershell
python -m venv backend\.venv
```

2) Instalar dependencias y migrar:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate
```

3) Levantar servidor:

```powershell
python manage.py runserver
```

API base:
- `http://localhost:8000/api/`

---

### Worker

En otra terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

python manage.py worker --sleep 2
```

Opciones:

```powershell
python manage.py worker --once
python manage.py worker --sleep 3
```

---

### Frontend (UI)

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## Variables de entorno

### Frontend

- `VITE_API_URL` — URL base del backend (sin `/api`)
  - recomendado: `http://localhost:8000`

Ejemplo en PowerShell:

```powershell
$env:VITE_API_URL="http://localhost:8000"
npm --prefix frontend run dev
```

---

## API (endpoints)

Base: `http://localhost:8000/api`

### Jobs

- `GET    /jobs/` — listar jobs
- `POST   /jobs/` — crear job (multipart: `preset`, `files[]`)
- `GET    /jobs/{id}/` — detalle de job
- `GET    /jobs/{id}/download/` — descargar ZIP del job

Acciones (si están habilitadas en el backend):

- `POST   /jobs/{id}/reprocess/`
- `POST   /jobs/{id}/pause/`
- `POST   /jobs/{id}/resume/`
- `POST   /jobs/{id}/cancel/`
- `DELETE /jobs/{id}/delete/`

### Job files (por archivo dentro del job)

- `PATCH /job-files/{id}/` — overrides por archivo (formato, calidad, metadatos, etc.)
- `PATCH /job-files/{id}/crop/` — guardar recorte manual
- `POST  /job-files/{id}/reprocess/` — reprocesar un archivo puntual

### Presets

- `GET    /presets/`
- `POST   /presets/custom/`
- `PATCH  /presets/custom/{id}/`
- `POST   /presets/custom/{id}/duplicate/`
- `DELETE /presets/custom/{id}/`

### Settings

- `GET   /settings/`
- `PATCH /settings/`
- `PUT   /settings/`

---

## Almacenamiento local

Carpeta principal:
- `backend/media/`

Rutas usadas por el backend:
- `backend/media/originals/` — originales
- `backend/media/outputs/` — salidas optimizadas
- `backend/media/zips/` — ZIP final por job

---

## Límites y formatos

Los límites se configuran en `backend/config/settings.py`.

Valores por defecto (si no se modificaron):
- `MAX_FILE_MB = 100`
- `MAX_JOB_MB  = 200`
- `MAX_IMAGE_MP = 100`

Formatos aceptados:
- JPEG (.jpg/.jpeg)
- PNG (.png)
- WebP (.webp)

---

## Funcionalidades del MVP

### Entregable final

Por cada job se genera un ZIP con:
- imágenes optimizadas
- `reporte.txt` (legible)
- `reporte.csv` (tabular)

### Reglas de negocio

- **No upscaling**: nunca se agranda una imagen por encima de su tamaño original.
- **Resize por modo**:
  - **CONTAIN**: encaja sin recortar.
  - **COVER**: llena y recorta (center crop).
  - Si COVER exige agrandar (upscaling), se usa CONTAIN.
- **Recorte manual**: si existe, tiene prioridad sobre recorte automático.
- **Metadatos**: se eliminan por defecto (configurable por settings u override).
- **Transparencia**:
  - se conserva en PNG/WebP,
  - si se exporta a JPG desde un original con transparencia, se aplica fondo según configuración.

### Pipeline por archivo (alto nivel)

1) Lectura segura  
2) Análisis (dimensiones, transparencia, metadatos)  
3) Ajustes efectivos (override → preset → defaults)  
4) Recorte (manual o automático)  
5) Resize final  
6) Exportación (formato/calidad/metadatos)  
7) Métricas antes/después (peso, dimensiones, ahorro)

---

## Backlog (priorizado)

### P0 (imprescindible)
- Subir imágenes por lote y elegir preset.
- Ver estado/progreso del job.
- Descargar ZIP final con reportes.
- Reporte antes/después por archivo.

### P1 (muy deseable)
- Overrides por archivo y reprocesado puntual.
- Recorte manual con relación de aspecto según preset.
- Presets personalizados (crear/editar/duplicar/eliminar).

### P2 (mejoras)
- Snippet HTML (`<img>` / `<picture>`) por resultado.
- Settings globales (defaults, concurrencia, límites).
- Comparativos por job (ahorro total, formatos, etc.).

---
