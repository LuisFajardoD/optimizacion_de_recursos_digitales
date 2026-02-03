from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import AppSettings, Job, JobFile, PresetCustom
from .presets import get_preset, list_presets_response, load_presets
from .serializers import AppSettingsSerializer, JobDetailSerializer, JobFileSerializer, JobSerializer
from .services import reprocess_job, reprocess_job_file


# Tipos MIME permitidos para cargas en el endpoint de jobs.
ALLOWED_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/jpg',
}


class JobViewSet(viewsets.ViewSet):
    parser_classes = [MultiPartParser, FormParser]

    def list(self, request):
        queryset = Job.objects.order_by('-created_at')
        serializer = JobSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        job = get_object_or_404(Job, pk=pk)
        serializer = JobDetailSerializer(job, context={'request': request})
        return Response(serializer.data)

    def create(self, request):
        """Crea un job y sus archivos asociados, validando límites y preset."""
        preset = request.data.get('preset')
        files = request.FILES.getlist('files')

        if not preset:
            return Response({'error': 'Debes seleccionar un preset.'}, status=status.HTTP_400_BAD_REQUEST)

        if not get_preset(preset):
            return Response(
                {'error': 'El preset seleccionado no existe.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not files:
            return Response({'error': 'Debes subir al menos un archivo.'}, status=status.HTTP_400_BAD_REQUEST)

        max_file_mb = getattr(settings, 'MAX_FILE_MB', 100)
        max_job_mb = getattr(settings, 'MAX_JOB_MB', 200)
        max_file_bytes = max_file_mb * 1024 * 1024
        max_job_bytes = max_job_mb * 1024 * 1024
        total_bytes = sum(file.size for file in files)

        if total_bytes > max_job_bytes:
            return Response(
                {'error': f'El total del trabajo excede {max_job_mb} MB.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for file in files:
            if file.content_type not in ALLOWED_CONTENT_TYPES:
                return Response(
                    {
                        'error': 'Formato no soportado. Convierte previamente a JPG/PNG/WEBP. '
                        'Ejemplo: HEIC/RAW.'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if file.size > max_file_bytes:
                return Response(
                    {'error': f'El archivo {file.name} excede el límite de {max_file_mb} MB.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        settings_obj, _created = AppSettings.objects.get_or_create(id=1)
        default_keep_metadata = not settings_obj.default_remove_metadata
        default_keep_transparency = settings_obj.default_keep_transparency

        job = Job.objects.create(preset=preset, total_files=len(files))

        for file in files:
            JobFile.objects.create(
                job=job,
                original_file=file,
                original_name=file.name,
                original_size=file.size,
                status=JobFile.Status.PENDING,
                keep_metadata=default_keep_metadata,
                keep_transparency=default_keep_transparency,
            )

        serializer = JobDetailSerializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Devuelve el ZIP de resultados si ya fue generado."""
        job = get_object_or_404(Job, pk=pk)
        if not job.result_zip:
            return Response({'error': 'ZIP no disponible.'}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(open(job.result_zip.path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{job.result_zip.name.rsplit("/", 1)[-1]}"'
        return response

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        job = get_object_or_404(Job, pk=pk)
        try:
            job = reprocess_job(job)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = JobDetailSerializer(job, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        job = get_object_or_404(Job, pk=pk)
        if job.status not in {Job.Status.PENDING, Job.Status.PROCESSING}:
            return Response({'error': 'El trabajo no se puede pausar en su estado actual.'}, status=status.HTTP_400_BAD_REQUEST)
        job.status = Job.Status.PAUSED
        job.save(update_fields=['status'])
        serializer = JobSerializer(job, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        job = get_object_or_404(Job, pk=pk)
        if job.status != Job.Status.PAUSED:
            return Response({'error': 'Solo se pueden reanudar trabajos en pausa.'}, status=status.HTTP_400_BAD_REQUEST)
        job.status = Job.Status.PENDING
        job.save(update_fields=['status'])
        serializer = JobSerializer(job, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        job = get_object_or_404(Job, pk=pk)
        if job.status in {Job.Status.DONE, Job.Status.FAILED, Job.Status.CANCELED}:
            return Response({'error': 'El trabajo ya terminó o fue cancelado.'}, status=status.HTTP_400_BAD_REQUEST)
        job.status = Job.Status.CANCELED
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'finished_at'])
        serializer = JobSerializer(job, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['delete'])
    def delete_job(self, request, pk=None):
        job = get_object_or_404(Job, pk=pk)
        if job.status in {Job.Status.PENDING, Job.Status.PROCESSING, Job.Status.PAUSED}:
            return Response(
                {'error': 'Solo se pueden borrar trabajos terminados o cancelados.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Elimina archivos asociados para evitar basura en disco.
        for job_file in job.files.all():
            if job_file.output_variants:
                storage = job_file.output_file.storage
                for variant in job_file.output_variants:
                    storage_name = variant.get('storage_name') or variant.get('name')
                    if storage_name and storage.exists(storage_name):
                        storage.delete(storage_name)

            if job_file.output_file:
                job_file.output_file.delete(save=False)
            if job_file.original_file:
                job_file.original_file.delete(save=False)

        if job.result_zip:
            job.result_zip.delete(save=False)

        job.delete()
        return Response({'success': True})


@api_view(['GET'])
def presets_view(request):
    return Response(list_presets_response())


@api_view(['GET', 'PUT', 'PATCH'])
def settings_view(request):
    """Lee y actualiza configuración global con validaciones básicas."""
    settings_obj, _created = AppSettings.objects.get_or_create(id=1)
    if request.method == 'GET':
        serializer = AppSettingsSerializer(settings_obj)
        return Response(serializer.data)

    data = request.data or {}
    updates = {}
    if 'concurrency' in data:
        concurrency = data.get('concurrency')
        try:
            concurrency = int(concurrency)
        except (TypeError, ValueError):
            return Response({'error': 'La concurrencia debe ser un número.'}, status=status.HTTP_400_BAD_REQUEST)
        if not (1 <= concurrency <= 10):
            return Response({'error': 'La concurrencia debe estar entre 1 y 10.'}, status=status.HTTP_400_BAD_REQUEST)
        updates['concurrency'] = concurrency

    if 'default_remove_metadata' in data:
        updates['default_remove_metadata'] = bool(data.get('default_remove_metadata'))

    if 'default_keep_transparency' in data:
        updates['default_keep_transparency'] = bool(data.get('default_keep_transparency'))

    if 'show_debug_details' in data:
        updates['show_debug_details'] = bool(data.get('show_debug_details'))

    for field, value in updates.items():
        setattr(settings_obj, field, value)

    if updates:
        settings_obj.save(update_fields=list(updates.keys()))
    serializer = AppSettingsSerializer(settings_obj)
    return Response(serializer.data)


@api_view(['PATCH'])
def job_file_crop_view(request, pk: int):
    """Guarda recorte manual normalizado (0..1) para un archivo."""
    job_file = get_object_or_404(JobFile, pk=pk)
    data = request.data or {}

    crop_mode = data.get('crop_mode')
    if crop_mode != 'manual':
        return Response(
            {'error': 'El recorte manual requiere crop_mode="manual".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        crop_x = float(data.get('crop_x'))
        crop_y = float(data.get('crop_y'))
        crop_w = float(data.get('crop_w'))
        crop_h = float(data.get('crop_h'))
    except (TypeError, ValueError):
        return Response({'error': 'Valores de recorte inválidos.'}, status=status.HTTP_400_BAD_REQUEST)

    if not (0 <= crop_x <= 1 and 0 <= crop_y <= 1):
        return Response({'error': 'crop_x y crop_y deben estar entre 0 y 1.'}, status=status.HTTP_400_BAD_REQUEST)
    if not (0 < crop_w <= 1 and 0 < crop_h <= 1):
        return Response({'error': 'crop_w y crop_h deben ser mayores que 0 y hasta 1.'}, status=status.HTTP_400_BAD_REQUEST)
    if crop_x + crop_w > 1 or crop_y + crop_h > 1:
        return Response({'error': 'El recorte debe estar dentro de la imagen.'}, status=status.HTTP_400_BAD_REQUEST)

    job_file.crop_mode = crop_mode
    job_file.crop_x = crop_x
    job_file.crop_y = crop_y
    job_file.crop_w = crop_w
    job_file.crop_h = crop_h
    job_file.save(update_fields=['crop_mode', 'crop_x', 'crop_y', 'crop_w', 'crop_h'])

    serializer = JobFileSerializer(job_file, context={'request': request})
    return Response(serializer.data)


@api_view(['PATCH'])
def job_file_update_view(request, pk: int):
    """Actualiza ajustes por archivo, con validaciones de formato/calidad/recorte."""
    job_file = get_object_or_404(JobFile, pk=pk)
    data = request.data or {}
    presets_data = load_presets()
    presets = {preset.get('id'): preset for preset in presets_data.get('presets', [])}

    selected_preset_id = data.get('selected_preset_id', job_file.selected_preset_id)
    if selected_preset_id:
        if selected_preset_id not in presets:
            return Response({'error': 'El preset seleccionado no existe.'}, status=status.HTTP_400_BAD_REQUEST)
        job_file.selected_preset_id = selected_preset_id
    elif 'selected_preset_id' in data:
        job_file.selected_preset_id = None

    output_format = data.get('output_format', job_file.output_format)
    if output_format:
        output_format = str(output_format).lower()
        if output_format not in {'webp', 'jpg', 'png', 'avif'}:
            return Response({'error': 'Formato no permitido.'}, status=status.HTTP_400_BAD_REQUEST)
        if output_format == 'avif':
            return Response(
                {'error': 'AVIF no está disponible en este entorno.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job_file.output_format = output_format
    elif 'output_format' in data:
        job_file.output_format = None

    if 'output_formats' in data:
        raw_formats = data.get('output_formats') or []
        if not isinstance(raw_formats, (list, tuple)):
            return Response({'error': 'Los formatos deben ser una lista.'}, status=status.HTTP_400_BAD_REQUEST)
        normalized = []
        for value in raw_formats:
            if value is None:
                continue
            fmt = str(value).lower()
            if fmt == 'avif':
                return Response(
                    {'error': 'AVIF no está disponible en este entorno.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if fmt not in {'webp', 'jpg', 'png'}:
                return Response({'error': 'Formato no permitido.'}, status=status.HTTP_400_BAD_REQUEST)
            if fmt not in normalized:
                normalized.append(fmt)
        if not normalized:
            return Response({'error': 'Selecciona al menos un formato.'}, status=status.HTTP_400_BAD_REQUEST)
        job_file.output_formats = normalized
        if not job_file.output_format or job_file.output_format not in normalized:
            job_file.output_format = normalized[0]

    for field in ('quality_webp', 'quality_jpg', 'quality_avif'):
        if field in data:
            value = data.get(field)
            if value is None or value == '':
                setattr(job_file, field, None)
                continue
            try:
                value = int(value)
            except (TypeError, ValueError):
                return Response({'error': f'{field} debe ser un número.'}, status=status.HTTP_400_BAD_REQUEST)
            if not (1 <= value <= 100):
                return Response({'error': 'La calidad debe estar entre 1 y 100.'}, status=status.HTTP_400_BAD_REQUEST)
            setattr(job_file, field, value)

    if 'keep_metadata' in data:
        job_file.keep_metadata = bool(data.get('keep_metadata'))

    if 'keep_transparency' in data:
        job_file.keep_transparency = bool(data.get('keep_transparency'))

    if 'rename_pattern' in data:
        job_file.rename_pattern = data.get('rename_pattern') or None

    if 'normalize_lowercase' in data:
        job_file.normalize_lowercase = bool(data.get('normalize_lowercase'))

    if 'normalize_remove_accents' in data:
        job_file.normalize_remove_accents = bool(data.get('normalize_remove_accents'))

    if 'normalize_replace_spaces' in data:
        job_file.normalize_replace_spaces = data.get('normalize_replace_spaces') or '-'

    if 'normalize_collapse_dashes' in data:
        job_file.normalize_collapse_dashes = bool(data.get('normalize_collapse_dashes'))

    if 'crop_enabled' in data:
        job_file.crop_enabled = bool(data.get('crop_enabled'))

    if 'crop_aspect' in data:
        job_file.crop_aspect = data.get('crop_aspect') or ''

    if 'generate_2x' in data:
        job_file.generate_2x = bool(data.get('generate_2x'))

    if 'generate_sharpened' in data:
        job_file.generate_sharpened = bool(data.get('generate_sharpened'))

    if job_file.generate_2x and job_file.generate_sharpened:
        return Response(
            {'error': 'No puedes activar 2x y Más nítido al mismo tiempo.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if any(key in data for key in ('crop_x', 'crop_y', 'crop_w', 'crop_h')):
        crop_x_raw = data.get('crop_x')
        crop_y_raw = data.get('crop_y')
        crop_w_raw = data.get('crop_w')
        crop_h_raw = data.get('crop_h')
        if crop_x_raw is None or crop_y_raw is None or crop_w_raw is None or crop_h_raw is None:
            job_file.crop_mode = 'manual'
            job_file.crop_x = None
            job_file.crop_y = None
            job_file.crop_w = None
            job_file.crop_h = None
        else:
            try:
                crop_x = float(crop_x_raw)
                crop_y = float(crop_y_raw)
                crop_w = float(crop_w_raw)
                crop_h = float(crop_h_raw)
            except (TypeError, ValueError):
                return Response({'error': 'Valores de recorte inválidos.'}, status=status.HTTP_400_BAD_REQUEST)
            if not (0 <= crop_x <= 1 and 0 <= crop_y <= 1):
                return Response({'error': 'crop_x y crop_y deben estar entre 0 y 1.'}, status=status.HTTP_400_BAD_REQUEST)
            if not (0 < crop_w <= 1 and 0 < crop_h <= 1):
                return Response({'error': 'crop_w y crop_h deben ser mayores que 0 y hasta 1.'}, status=status.HTTP_400_BAD_REQUEST)
            if crop_x + crop_w > 1 or crop_y + crop_h > 1:
                return Response({'error': 'El recorte debe estar dentro de la imagen.'}, status=status.HTTP_400_BAD_REQUEST)
            job_file.crop_mode = 'manual'
            job_file.crop_x = crop_x
            job_file.crop_y = crop_y
            job_file.crop_w = crop_w
            job_file.crop_h = crop_h

    job_file.save()
    serializer = JobFileSerializer(job_file, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
def job_file_reprocess_view(request, pk: int):
    """Reprocesa un archivo y actualiza el ZIP del job."""
    job_file = get_object_or_404(JobFile, pk=pk)
    try:
        job = reprocess_job_file(job_file)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    serializer = JobDetailSerializer(job, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
def presets_custom_create(request):
    """Crea un preset personalizado con validaciones mínimas."""
    data = request.data or {}
    required_fields = ['id', 'label', 'category', 'width', 'height', 'aspect']
    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        return Response(
            {'error': f'Faltan campos obligatorios: {", ".join(missing)}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    error = _validate_preset_payload(data, require_id=True)
    if error:
        return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

    preset_id = str(data.get('id')).strip()
    if get_preset(preset_id):
        return Response({'error': 'El id ya existe en los presets base o personalizados.'}, status=status.HTTP_400_BAD_REQUEST)

    preset = PresetCustom.objects.create(
        preset_id=preset_id,
        label=str(data.get('label')).strip(),
        category=str(data.get('category')).strip(),
        width=int(data.get('width')),
        height=int(data.get('height')),
        aspect=str(data.get('aspect')).strip(),
        type_hint=str(data.get('typeHint') or 'photo').strip().lower(),
        density=str(data.get('density') or 'standard').strip(),
        recommended_format=str(data.get('recommendedFormat') or '').strip().lower(),
    )
    return Response(_serialize_custom_preset(preset), status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
def presets_custom_update(request, preset_id: str):
    """Edita o elimina un preset personalizado existente."""
    preset = get_object_or_404(PresetCustom, preset_id=preset_id)
    if request.method == 'DELETE':
        preset.delete()
        return Response({'success': True})

    data = request.data or {}
    error = _validate_preset_payload(data, require_id=False)
    if error:
        return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

    for field, key in (
        ('label', 'label'),
        ('category', 'category'),
        ('width', 'width'),
        ('height', 'height'),
        ('aspect', 'aspect'),
        ('type_hint', 'typeHint'),
        ('density', 'density'),
        ('recommended_format', 'recommendedFormat'),
    ):
        if key in data:
            value = data.get(key)
            if field in {'width', 'height'} and value is not None:
                value = int(value)
            if field in {'type_hint', 'recommended_format'} and value is not None:
                value = str(value).strip().lower()
            setattr(preset, field, value)

    preset.save()
    return Response(_serialize_custom_preset(preset))


@api_view(['POST'])
def presets_custom_duplicate(request, preset_id: str):
    """Duplica un preset personalizado, generando un id libre."""
    preset = get_object_or_404(PresetCustom, preset_id=preset_id)
    new_id = _next_custom_id(preset.preset_id)
    new_preset = PresetCustom.objects.create(
        preset_id=new_id,
        label=f"{preset.label} (copia)",
        category=preset.category,
        width=preset.width,
        height=preset.height,
        aspect=preset.aspect,
        type_hint=preset.type_hint,
        density=preset.density,
        recommended_format=preset.recommended_format,
    )
    return Response(_serialize_custom_preset(new_preset), status=status.HTTP_201_CREATED)




def _validate_preset_payload(data: dict, require_id: bool) -> str:
    """Valida campos base de presets personalizados y retorna error legible."""
    if require_id and not data.get('id'):
        return 'El id es obligatorio.'
    if 'label' in data and not str(data.get('label')).strip():
        return 'El label es obligatorio.'
    if 'category' in data:
        category = str(data.get('category')).strip()
        if not category:
            return 'La categoría es obligatoria.'
    if 'width' in data:
        try:
            width = int(data.get('width'))
        except (TypeError, ValueError):
            return 'El ancho debe ser un número.'
        if width <= 0:
            return 'El ancho debe ser mayor que 0.'
    if 'height' in data:
        try:
            height = int(data.get('height'))
        except (TypeError, ValueError):
            return 'El alto debe ser un número.'
        if height <= 0:
            return 'El alto debe ser mayor que 0.'
    if 'aspect' in data:
        aspect = str(data.get('aspect')).strip()
        if not aspect or ':' not in aspect:
            return 'El aspect debe tener formato W:H.'
        try:
            w, h = aspect.split(':', 1)
            if float(w) <= 0 or float(h) <= 0:
                return 'El aspect debe tener números mayores que 0.'
        except ValueError:
            return 'El aspect debe tener números válidos.'
    if 'typeHint' in data:
        value = str(data.get('typeHint')).strip()
        if value not in {'photo', 'ui'}:
            return 'typeHint debe ser "photo" o "ui".'
    if 'density' in data:
        value = str(data.get('density')).strip()
        if value not in {'standard', 'suggestHigherDpi'}:
            return 'density inválido.'
    if 'recommendedFormat' in data and data.get('recommendedFormat'):
        value = str(data.get('recommendedFormat')).strip().lower()
        if value not in {'webp', 'jpg', 'png'}:
            return 'recommendedFormat inválido.'
    return ''


def _next_custom_id(base_id: str) -> str:
    """Genera un id disponible para duplicados."""
    candidate = f"{base_id}-copy"
    counter = 2
    while PresetCustom.objects.filter(preset_id=candidate).exists() or get_preset(candidate):
        candidate = f"{base_id}-copy-{counter}"
        counter += 1
    return candidate


def _serialize_custom_preset(preset: PresetCustom) -> dict:
    return {
        'id': preset.preset_id,
        'label': preset.label,
        'category': preset.category,
        'width': preset.width,
        'height': preset.height,
        'aspect': preset.aspect,
        'typeHint': preset.type_hint,
        'recommendedFormat': preset.recommended_format or None,
        'density': preset.density,
        'source': 'custom',
    }
