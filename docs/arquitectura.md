# Arquitectura - Proyecto VIII

## Flujo principal
1. Se selecciona un preset y se cargan imágenes desde la vista de subida.
2. El frontend envía multipart a POST /api/jobs/ (si hay más de 10 archivos se crean varios jobs).
3. El backend valida límites, crea Job/JobFile y deja el job en PENDING.
4. El worker local toma jobs PENDING con concurrencia configurable y procesa cada archivo:
   - análisis automático,
   - recorte/resize según preset y ajustes,
   - generación de salidas y variantes.
5. Se genera un ZIP con imágenes optimizadas y reportes TXT/CSV.
6. La UI consulta GET /api/jobs/ y GET /api/jobs/{id}/ para estado y detalle.
7. La descarga del ZIP se realiza con GET /api/jobs/{id}/download/.

## Componentes
- Frontend (React + Vite + TS): UploadPage, JobsPage, JobDetailPage, SettingsPage.
- Backend (Django + DRF): modelos Job/JobFile, endpoints REST, presets base + personalizados.
- Worker local: comando `manage.py worker` con pool de hilos.
- Almacenamiento local: media/originals, media/outputs, media/zips.

## Funcionalidades clave
- Ajustes por archivo (formato, calidad, metadatos, transparencia, naming).
- Recorte manual con relación de aspecto bloqueada por preset.
- Reportes legibles dentro del ZIP (TXT/CSV).
- Presets personalizados y configuración global (concurrencia, defaults).

## Endpoints base
- POST /api/jobs/ (multipart: preset, files[])
- GET /api/jobs/
- GET /api/jobs/{id}/
- GET /api/jobs/{id}/download/
