# Funcionalidades del MVP — Optimización por jobs

## Descripción general

El MVP permite **optimizar imágenes por lote** usando trabajos (**jobs**). El flujo está pensado para:

- subir varias imágenes,
- procesarlas en segundo plano,
- ajustar por archivo si se necesita,
- descargar un ZIP con resultados y reportes.

---

## Entregable final (ZIP)

Por cada job se genera un ZIP que incluye:

- imágenes optimizadas (salida final),
- `reporte.txt` (legible para humanos),
- `reporte.csv` (tabular para Excel/Sheets).

Contenido típico del ZIP (referencia):

- `/outputs/` (o raíz) → imágenes finales
- `reporte.txt`
- `reporte.csv`

---

## Reglas de negocio clave

### 1) No upscaling
Nunca se agranda una imagen por encima de su tamaño original.

- Si el preset pide un ancho mayor al original, se respeta el original.
- Si una regla exige “llenar” (COVER) pero eso implicaría agrandar, se ajusta el comportamiento (ver Resize).

### 2) Resize por modo
Dos modos principales:

- **CONTAIN**: encaja dentro del tamaño objetivo sin recortar.
- **COVER**: llena el tamaño objetivo y recorta (center crop por defecto).

Regla práctica:
- Si **COVER** implica upscaling, se usa **CONTAIN**.

### 3) Recorte manual (prioridad)
Si el usuario define recorte manual, ese recorte se aplica antes que cualquier recorte automático.

- El recorte manual se guarda por archivo.
- El reprocesado usa el recorte guardado.

### 4) Metadatos
Por defecto se eliminan (para reducir peso y privacidad), pero debe ser configurable:

- settings globales (default),
- preset,
- override por archivo.

### 5) Transparencia
Se maneja según formato final:

- PNG/WebP: se conserva transparencia (alpha) si existe.
- JPG: no soporta alpha; si el original tiene transparencia, se aplica fondo (según configuración).

### 6) Overrides por archivo
Cada archivo dentro del job puede tener ajustes independientes:

- cambiar formato final,
- cambiar calidad,
- mantener/eliminar metadatos,
- cambiar fondo/alpha handling,
- (si aplica) modificar max width / modo de resize.

Al cambiar overrides:
- se reprocesa solo ese archivo (si el endpoint/feature está habilitado).

---

## Pipeline de procesamiento por archivo (alto nivel)

1) **Lectura segura**
   - Carga del archivo original desde `media/originals/`.
   - Validación básica (existencia, formato real).

2) **Análisis**
   - dimensiones (ancho/alto),
   - megapíxeles,
   - orientación,
   - transparencia (alpha),
   - metadatos.

3) **Cálculo de ajustes efectivos** (prioridad)
   1. override por archivo (si existe)
   2. preset asignado al job
   3. defaults globales (settings)

4) **Recorte**
   - manual si existe,
   - automático si aplica (por ejemplo center crop en COVER).

5) **Resize final**
   - según `max_width`/target y `resize_mode` (CONTAIN/COVER),
   - respetando **no upscaling**.

6) **Exportación**
   - formato final (JPG/PNG/WebP),
   - calidad (si aplica),
   - metadatos (keep/remove),
   - manejo de transparencia/fondo.

7) **Métricas y registro**
   - tamaño antes/después (bytes),
   - dimensiones finales,
   - formato final,
   - porcentaje aproximado de reducción.

---

## Funcionalidades de UI (MVP)

### Carga y creación de job
- Selección de preset.
- Subida por lote (multiple files).
- Validaciones y feedback (si el backend rechaza por límites).

### Vista de jobs
- Lista de jobs con:
  - estado,
  - total de archivos,
  - progreso (procesados vs total),
  - fecha de creación (si aplica).

### Detalle de job
- Lista de archivos del job con su estado individual:
  - `PENDING`, `RUNNING`, `DONE`, `FAILED`.
- Información por archivo:
  - nombre,
  - tamaño antes/después,
  - formato final,
  - link a preview (si aplica).

### Ajustes por archivo (si está habilitado)
- Overrides de:
  - formato,
  - calidad,
  - metadatos,
  - transparencia/fondo.
- Reprocesado puntual del archivo.

### Recorte manual (si está habilitado)
- Selector de recorte con coordenadas normalizadas.
- Reprocesado con recorte guardado.

### Descarga
- Botón de descarga de ZIP del job cuando esté en `DONE`.

---

## Estados y operación (referencia)

Estados sugeridos:

- `PENDING`: creado, esperando procesamiento
- `RUNNING`: en proceso
- `DONE`: terminado correctamente
- `FAILED`: error en procesamiento
- `PAUSED`: pausado por acción (si aplica)
- `CANCELED`: cancelado por acción (si aplica)

Operación:
- Si el **worker** no está ejecutándose, los jobs se quedan en `PENDING`.
- El worker procesa de forma continua con un `--sleep N` entre ciclos.

---

## Reportes (qué deben incluir)

### reporte.txt (humano)
Por archivo:
- nombre original,
- tamaño antes/después,
- formato final,
- dimensiones finales,
- ahorro aproximado.

Resumen:
- total de archivos,
- total de bytes antes/después,
- ahorro total (bytes y %).

### reporte.csv (tabla)
Columnas sugeridas:
- filename
- status
- input_bytes
- output_bytes
- input_width
- input_height
- output_width
- output_height
- output_format
- saved_bytes
- saved_percent

---

## Límites y validaciones (referencia)

- Tamaño máximo por archivo (MB).
- Tamaño máximo por job (MB).
- Megapíxeles máximos por imagen.
- Formatos permitidos.

Estos límites se configuran en settings del backend.
