# API — Endpoints y ejemplos

Base local:
- `http://localhost:8000/api`

Convenciones:
- Respuestas en JSON.
- Subida de archivos vía `multipart/form-data`.
- IDs numéricos en rutas: `{id}`.

---

## Jobs

### Listar jobs
`GET /jobs/`

Respuesta (ejemplo, resumen):
```json
[
  {
    "id": 12,
    "status": "PENDING",
    "preset": "web-default",
    "total_files": 10,
    "processed_files": 0,
    "created_at": "2026-02-02T12:00:00Z"
  }
]
```

### Crear job (subir imágenes)
`POST /jobs/`

`multipart/form-data`:
- `preset`: string
- `files[]`: archivos

Respuesta típica:
```json
{
  "id": 12,
  "status": "PENDING",
  "total_files": 10
}
```

Notas:
- Si se cargan **más de 10 imágenes**, el backend puede dividir la carga en varios jobs (según configuración/implementación).

### Detalle de job
`GET /jobs/{id}/`

Respuesta (ejemplo simplificado):
```json
{
  "id": 12,
  "status": "RUNNING",
  "preset": "web-default",
  "total_files": 10,
  "processed_files": 3,
  "files": [
    {
      "id": 1201,
      "filename": "foto-1.png",
      "status": "DONE",
      "input_bytes": 523000,
      "output_bytes": 141000,
      "format": "webp"
    }
  ]
}
```

Campos comunes (referencia):
- `status`: `PENDING | RUNNING | DONE | FAILED | PAUSED | CANCELED`
- `total_files`: total de archivos en el job
- `processed_files`: cuántos ya fueron procesados
- `files`: lista de archivos con su estado y métricas (si aplica)

### Descargar ZIP del job
`GET /jobs/{id}/download/`

- Devuelve un archivo ZIP (binary).
- Contiene salidas + `reporte.txt` + `reporte.csv` (si aplica).

### Acciones del job (si están habilitadas)

Reprocesar job completo:
- `POST /jobs/{id}/reprocess/`

Control de ejecución:
- `POST /jobs/{id}/pause/`
- `POST /jobs/{id}/resume/`

Cancelar job:
- `POST /jobs/{id}/cancel/`

Eliminar job:
- `DELETE /jobs/{id}/delete/`

---

## Job files (por archivo dentro del job)

### Overrides por archivo
`PATCH /job-files/{id}/`

Body (ejemplo):
```json
{
  "format": "webp",
  "quality": 78,
  "keep_metadata": false,
  "transparent_bg": true
}
```

Campos típicos (referencia, según implementación):
- `format`: `jpg | png | webp`
- `quality`: entero 1..100 (para formatos con compresión con pérdida)
- `keep_metadata`: boolean
- `transparent_bg`: boolean (manejo de transparencia, si aplica)
- `max_width`: número (si se permite override)
- `resize_mode`: `CONTAIN | COVER` (si se permite override)

### Guardar recorte manual
`PATCH /job-files/{id}/crop/`

Coordenadas normalizadas 0..1:
```json
{
  "x": 0.10,
  "y": 0.05,
  "w": 0.80,
  "h": 0.90
}
```

Reglas:
- El recorte manual, si existe, tiene prioridad sobre el recorte automático.
- El backend valida rangos y valores mínimos.

### Reprocesar un archivo puntual
`POST /job-files/{id}/reprocess/`

- Recalcula el resultado del archivo con overrides y/o recorte actual.

---

## Presets

### Listar presets
`GET /presets/`

- Devuelve presets base y personalizados (si aplica).

### Crear preset personalizado
`POST /presets/custom/`

Body (ejemplo):
```json
{
  "name": "web-compact",
  "format": "webp",
  "quality": 78,
  "max_width": 1600,
  "resize_mode": "CONTAIN",
  "keep_metadata": false
}
```

### Editar preset personalizado
`PATCH /presets/custom/{id}/`

### Duplicar preset personalizado
`POST /presets/custom/{id}/duplicate/`

### Eliminar preset personalizado
`DELETE /presets/custom/{id}/`

---

## Settings

### Leer settings globales
`GET /settings/`

### Actualizar parcialmente settings
`PATCH /settings/`

### Reemplazar settings
`PUT /settings/`

Campos típicos (referencia, según implementación):
- `MAX_FILE_MB`
- `MAX_JOB_MB`
- `MAX_IMAGE_MP`
- defaults para formato/calidad/resize
- concurrencia del worker (si aplica)

---

## Errores comunes (referencia)

- `400 Bad Request`: validación (preset inválido, campos faltantes, crop inválido)
- `404 Not Found`: id inexistente
- `413 Payload Too Large`: archivo/job excede límites
- `415 Unsupported Media Type`: formato no permitido
- `500 Internal Server Error`: error inesperado en procesamiento

---

## Ejemplos con cURL (opcional)

Crear job:
```bash
curl -X POST "http://localhost:8000/api/jobs/" \
  -F "preset=web-default" \
  -F "files[]=@/ruta/a/imagen1.jpg" \
  -F "files[]=@/ruta/a/imagen2.png"
```

Detalle job:
```bash
curl "http://localhost:8000/api/jobs/12/"
```

Descargar ZIP:
```bash
curl -L "http://localhost:8000/api/jobs/12/download/" -o job-12.zip
```
