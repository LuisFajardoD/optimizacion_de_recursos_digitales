# Backlog MVP — Optimización de Recursos Digitales (Jobs)

## P0 (Imprescindible)

### US-01 — Subir imágenes por lote y crear job
**Como usuario**, quiero subir varias imágenes en un lote para crear un job de optimización, **para** procesarlas de forma automática y ordenada.

**Criterios de aceptación**
- Permite seleccionar múltiples archivos en una sola carga.
- La carga se envía como `multipart/form-data` con `preset` y `files[]`.
- El sistema valida:
  - formato permitido (JPG/PNG/WebP),
  - tamaño máximo por archivo,
  - tamaño máximo por job,
  - megapíxeles máximos por imagen.
- Si algo falla, devuelve un error claro (por ejemplo `400/413/415`) y no crea un job inconsistente.
- Al finalizar la carga, se muestra el `id` del job y su estado inicial (`PENDING`).

**Notas**
- Si se suben más de 10 imágenes, el backend puede dividir en varios jobs (si esa regla está activa).

---

### US-02 — Elegir preset para controlar salida
**Como usuario**, quiero elegir un preset antes de subir imágenes, **para** definir reglas de salida (formato, calidad, ancho máximo, modo de resize, metadatos).

**Criterios de aceptación**
- La UI permite seleccionar un preset visible por nombre.
- El preset queda guardado en el job creado.
- El preset impacta el procesamiento del worker (salida final coherente con el preset).

---

### US-03 — Ver lista de jobs con estado y progreso
**Como usuario**, quiero ver una lista de jobs con su estado y progreso, **para** saber qué ya terminó y qué sigue procesándose.

**Criterios de aceptación**
- La lista muestra por job:
  - `id`,
  - `status` (PENDING/RUNNING/DONE/FAILED),
  - total de archivos,
  - procesados vs total,
  - fecha/hora (si aplica).
- Si el worker no está corriendo, el job se queda en `PENDING` y la UI lo refleja.

---

### US-04 — Ver detalle de job y archivos
**Como usuario**, quiero entrar al detalle de un job y ver el estado por archivo, **para** identificar fallas y validar resultados.

**Criterios de aceptación**
- En el detalle del job se lista cada archivo con:
  - nombre,
  - estado por archivo,
  - tamaño antes/después (si ya procesó),
  - formato final (si ya procesó).
- Si un archivo falla, se marca como `FAILED` y el job refleja el estado general correspondiente.

---

### US-05 — Descargar ZIP del job terminado
**Como usuario**, quiero descargar un ZIP con las imágenes optimizadas, **para** obtener el entregable final en un solo archivo.

**Criterios de aceptación**
- La descarga está disponible cuando el job está en `DONE` (o cuando existan resultados listos).
- El ZIP contiene:
  - imágenes optimizadas,
  - `reporte.txt`,
  - `reporte.csv`.
- Si el job no está listo, la descarga responde con error controlado (o la UI deshabilita el botón).

---

### US-06 — Generar reporte antes/después por archivo
**Como usuario**, quiero ver un reporte antes/después por archivo, **para** comprobar el beneficio (ahorro y características finales).

**Criterios de aceptación**
- `reporte.txt` incluye por archivo:
  - nombre,
  - bytes antes/después,
  - dimensiones finales,
  - formato final,
  - ahorro (bytes y %).
- `reporte.csv` incluye una tabla con columnas consistentes:
  - filename, status, input_bytes, output_bytes, output_width, output_height, output_format, saved_bytes, saved_percent.
- El reporte resume ahorro total del job.

---

## P1 (Muy deseable)

### US-07 — Overrides por archivo y reprocesado puntual
**Como usuario**, quiero ajustar parámetros por archivo (formato, calidad, metadatos, etc.) y reprocesar solo ese archivo, **para** corregir casos especiales sin reprocesar todo el job.

**Criterios de aceptación**
- Permite guardar overrides por archivo.
- Permite reprocesar solo ese archivo.
- El resultado y reportes se actualizan para ese archivo.

---

### US-08 — Recorte manual por archivo
**Como usuario**, quiero recortar manualmente una imagen, **para** controlar el encuadre cuando el recorte automático no es suficiente.

**Criterios de aceptación**
- Permite definir crop (x,y,w,h normalizados 0..1).
- El recorte manual tiene prioridad sobre recorte automático.
- Reprocesar aplica el crop guardado.

---

### US-09 — Presets personalizados (CRUD)
**Como usuario**, quiero crear, editar, duplicar y eliminar presets personalizados, **para** reutilizar configuraciones sin repetir ajustes.

**Criterios de aceptación**
- Crear preset con nombre y parámetros principales.
- Editar preset existente.
- Duplicar preset y modificarlo.
- Eliminar preset personalizado (sin afectar presets base).

---

## P2 (Mejoras)

### US-10 — Snippet HTML por imagen optimizada
**Como usuario**, quiero obtener un snippet HTML (`<img>` o `<picture>`), **para** integrar rápido los resultados en una web.

### US-1 — Ajustes globales (settings)
**Como usuario administrador**, quiero configurar límites y defaults globales, **para** adaptar el sistema a diferentes escenarios de uso (MVP/producción).
