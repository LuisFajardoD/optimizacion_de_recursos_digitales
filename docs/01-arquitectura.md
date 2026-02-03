# Arquitectura — Flujo general (MVP)

## Objetivo

Optimizar imágenes por lote mediante un flujo de **jobs**:
- el usuario sube imágenes,
- el backend registra el trabajo,
- el worker procesa en segundo plano,
- al final se descarga un ZIP con resultados y reportes.

---

## Flujo principal (end-to-end)

1) **UI (Frontend)**
   - El usuario selecciona un **preset**.
   - Sube imágenes desde la pantalla de carga.

2) **Creación de job (Backend)**
   - La UI envía `multipart/form-data` a:
     - `POST /api/jobs/` con `preset` y `files[]`
   - Regla operativa:
     - si se cargan **más de 10 imágenes**, se divide en varios jobs.

3) **Registro y validación**
   - El backend valida:
     - tamaño máximo por archivo,
     - tamaño máximo por job,
     - megapíxeles máximos por imagen,
     - formatos permitidos.
   - Crea entidades:
     - `Job` (trabajo)
     - `JobFile` (archivo dentro del trabajo)
   - El job queda en estado **PENDING**.

4) **Procesamiento (Worker local)**
   - El worker consulta trabajos en `PENDING` y los procesa.
   - Para cada archivo:
     - lectura segura,
     - análisis automático (dimensiones, transparencia, tipo, metadatos),
     - recorte/resize según preset y overrides,
     - exportación al formato final,
     - métricas antes/después.

5) **Generación de entregables**
   - Se genera un **ZIP** por job con:
     - imágenes optimizadas,
     - `reporte.txt` (humano),
     - `reporte.csv` (tabla para Excel/Sheets).

6) **Consulta de estado y descarga**
   - La UI consulta:
     - `GET /api/jobs/` (lista)
     - `GET /api/jobs/{id}/` (detalle)
   - Descarga:
     - `GET /api/jobs/{id}/download/`

---

## Componentes

### Frontend (React + Vite + TypeScript)
Responsable de:
- carga de imágenes por lote,
- listado de jobs y estados,
- detalle por job y por archivo,
- ajustes por archivo (overrides),
- recorte manual y vista previa,
- descarga de ZIP,
- settings/presets (si aplica).

### Backend (Django + DRF)
Responsable de:
- endpoints REST,
- validaciones y límites,
- modelos `Job` / `JobFile`,
- presets base y personalizados,
- settings globales,
- almacenamiento de originales/salidas/ZIP,
- consolidación de reportes.

### Worker local (comando Django)
Responsable de:
- tomar jobs `PENDING`,
- procesar archivos,
- actualizar progreso y resultados,
- generar ZIP y reportes.
No depende de Celery/Redis en el MVP.

---

## Estados sugeridos (referencia)

- `PENDING`: creado, esperando procesamiento
- `RUNNING`: en proceso
- `DONE`: finalizado correctamente
- `FAILED`: error en procesamiento
- `PAUSED`: pausado por acción (si está habilitado)
- `CANCELED`: cancelado por acción (si está habilitado)

---

## Almacenamiento local (media)

Carpeta base: `backend/media/`

- `backend/media/originals/` — archivos originales
- `backend/media/outputs/` — salidas optimizadas
- `backend/media/zips/` — ZIP final por job

---

## Decisiones de diseño (MVP)

- Procesamiento en background con **worker local** para simplicidad.
- Jobs por lote para:
  - controlar límites,
  - permitir progreso,
  - soportar reprocesos parciales por archivo.
- Reportes dentro del ZIP para que el entregable sea autocontenido.
