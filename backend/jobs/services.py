import errno
import math
import os
import unicodedata
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from .models import AppSettings, Job, JobFile
from .presets import get_preset, infer_category, load_presets

SUPPORTED_FORMATS = {'webp', 'jpg', 'png'}
NO_UPSCALE_NOTE = (
    "Sin upscaling: el original es menor que el objetivo; se exportó al máximo posible."
)


def _human_error_message(exc: Exception) -> str:
    """Mapea excepciones comunes a mensajes legibles en español.

    Si está habilitado el modo de depuración, agrega el tipo de excepción.
    """
    settings_obj = AppSettings.objects.filter(id=1).first()
    debug = bool(
        getattr(settings, 'SHOW_TECH_ERRORS', False)
        or settings.DEBUG
        or (settings_obj.show_debug_details if settings_obj else False)
    )

    if isinstance(exc, UnidentifiedImageError):
        message = 'No se pudo leer la imagen. Verifica que sea JPG/PNG/WEBP.'
    elif isinstance(exc, MemoryError):
        message = 'Memoria insuficiente para procesar la imagen.'
    elif isinstance(exc, PermissionError):
        message = 'Permisos insuficientes en carpeta de salida del servidor.'
    elif isinstance(exc, OSError) and getattr(exc, 'errno', None) == errno.ENOSPC:
        message = 'Espacio insuficiente para generar resultados. Libera espacio.'
    elif isinstance(exc, ValueError) and str(exc):
        message = str(exc)
    else:
        message = 'Ocurrió un error al procesar la imagen.'

    if debug:
        message = f"{message} (detalle: {exc.__class__.__name__})"
    return message


def process_job(job: Job) -> None:
    """Procesa un job completo: aplica preset, genera outputs y arma el ZIP final.

    Respeta pausas/cancelaciones y actualiza progreso y estados por archivo.
    """
    if job.status in {Job.Status.PAUSED, Job.Status.CANCELED}:
        return
    preset = get_preset(job.preset)
    if not preset:
        job.status = Job.Status.FAILED
        job.error_message = 'El preset del trabajo no existe.'
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'finished_at'])
        return

    presets_data = load_presets()
    defaults = presets_data.get('defaults', {})
    output_format = _resolve_format(preset, defaults)
    quality = _resolve_quality(preset, defaults)
    resize_mode = _resolve_resize_mode(preset, defaults)
    no_upscale = defaults.get('resize', {}).get('noUpscale', True)
    target_size = (preset.get('width'), preset.get('height'))

    job.status = Job.Status.PROCESSING
    job.started_at = timezone.now()
    job.progress = 0
    job.processed_files = 0
    job.error_message = ''
    job.save(update_fields=['status', 'started_at', 'progress', 'processed_files', 'error_message'])

    errors = False
    report_rows = []

    # Evita colisiones de nombres dentro del ZIP cuando hay renombrado similar.
    used_names: set[str] = set()
    for index, job_file in enumerate(job.files.all(), start=1):
        job.refresh_from_db(fields=['status'])
        if job.status == Job.Status.PAUSED:
            job.save(update_fields=['status'])
            return
        if job.status == Job.Status.CANCELED:
            job.finished_at = timezone.now()
            job.save(update_fields=['status', 'finished_at'])
            return

        job_file.status = JobFile.Status.PROCESSING
        job_file.save(update_fields=['status'])

        try:
            output_bytes, output_name, report_meta = _process_job_file(
                job_file,
                job,
                target_size,
                resize_mode,
                output_format,
                quality,
                no_upscale=no_upscale,
                presets_data=presets_data,
                defaults=defaults,
                used_names=used_names,
            )
            _save_job_file_output(
                job_file,
                output_name,
                output_bytes,
                report_meta.get('output_width'),
                report_meta.get('output_height'),
            )
        except Exception as exc:
            errors = True
            job_file.status = JobFile.Status.FAILED
            job_file.error_message = _human_error_message(exc)
            job_file.save(update_fields=['status', 'error_message'])
            report_meta = _derive_report_meta(job_file, preset, defaults)

        job.processed_files = index
        job.progress = int((job.processed_files / job.total_files) * 100) if job.total_files else 0
        job.save(update_fields=['processed_files', 'progress'])

        report_rows.append(_build_report_row(job_file, report_meta))

    try:
        zip_path = _build_zip(job, preset, report_rows, output_format)
        if zip_path:
            job.result_zip.name = zip_path
        else:
            errors = True
            job.error_message = 'No se pudo generar el ZIP de resultados.'
    except Exception as exc:
        errors = True
        job.error_message = _human_error_message(exc)

    job.status = Job.Status.FAILED if errors else Job.Status.DONE
    job.finished_at = timezone.now()
    job.save(update_fields=['status', 'finished_at', 'result_zip', 'error_message'])


def reprocess_job_file(job_file: JobFile) -> Job:
    """Reprocesa un archivo puntual y reconstruye el ZIP del trabajo."""
    job = job_file.job
    preset = get_preset(job.preset)
    if not preset:
        raise ValueError('El preset del trabajo no existe.')

    presets_data = load_presets()
    defaults = presets_data.get('defaults', {})
    output_format = _resolve_format(preset, defaults)
    quality = _resolve_quality(preset, defaults)
    resize_mode = _resolve_resize_mode(preset, defaults)
    no_upscale = defaults.get('resize', {}).get('noUpscale', True)
    target_size = (preset.get('width'), preset.get('height'))

    job.status = Job.Status.PROCESSING
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'started_at'])

    job_file.status = JobFile.Status.PROCESSING
    job_file.error_message = ''
    job_file.save(update_fields=['status', 'error_message'])

    used_names = {
        file.output_name for file in job.files.exclude(id=job_file.id) if file.output_name
    }
    try:
        output_bytes, output_name, report_meta = _process_job_file(
            job_file,
            job,
            target_size,
            resize_mode,
            output_format,
            quality,
            no_upscale=no_upscale,
            presets_data=presets_data,
            defaults=defaults,
            used_names=used_names,
        )
        _save_job_file_output(
            job_file,
            output_name,
            output_bytes,
            report_meta.get('output_width'),
            report_meta.get('output_height'),
        )
    except Exception as exc:
        job_file.status = JobFile.Status.FAILED
        job_file.error_message = _human_error_message(exc)
        job_file.save(update_fields=['status', 'error_message'])
        raise

    report_rows = _collect_report_rows(job, preset, defaults, {job_file.id: report_meta})
    try:
        zip_path = _build_zip(job, preset, report_rows, output_format)
        if zip_path:
            job.result_zip.name = zip_path
        else:
            job.status = Job.Status.FAILED
            job.error_message = 'No se pudo generar el ZIP de resultados.'
    except Exception as exc:
        job.status = Job.Status.FAILED
        job.error_message = _human_error_message(exc)

    job.processed_files = job.files.count()
    job.progress = 100
    if job.status != Job.Status.FAILED:
        job.status = Job.Status.DONE
    job.finished_at = timezone.now()
    job.save(update_fields=['processed_files', 'progress', 'status', 'finished_at', 'result_zip', 'error_message'])
    return job


def reprocess_job(job: Job) -> Job:
    """Reinicia el estado del job y reprocesa todos sus archivos."""
    job.status = Job.Status.PENDING
    job.started_at = None
    job.finished_at = None
    job.progress = 0
    job.processed_files = 0
    job.error_message = ''
    job.save(update_fields=['status', 'started_at', 'finished_at', 'progress', 'processed_files', 'error_message'])

    job.files.update(status=JobFile.Status.PENDING, error_message='')
    process_job(job)
    return job


def _prepare_image(
    image: Image.Image,
    target_size: Tuple[Optional[int], Optional[int]],
    resize_mode: str,
    no_upscale: bool = True,
    crop_data: Optional[dict] = None,
    keep_alpha: bool = False,
) -> Tuple[Image.Image, dict]:
    """Aplica recorte manual (si existe) y resize según modo y tamaño objetivo.

    Retorna la imagen preparada y metadatos para el reporte.
    """
    image = _ensure_mode(image, keep_alpha)
    target_width, target_height = target_size
    input_width, input_height = image.size
    report_meta = {
        'input_width': input_width,
        'input_height': input_height,
        'output_width': input_width,
        'output_height': input_height,
        'resize_mode': None,
        'no_upscale_applied': False,
        'note': '',
    }

    if not target_width or not target_height:
        return image, report_meta

    if crop_data and crop_data.get('crop_mode') == 'manual':
        image = _apply_manual_crop(image, crop_data)
        report_meta['note'] = 'Recorte manual aplicado.'

    if resize_mode == 'cover':
        resized, note = _resize_cover(image, target_width, target_height, no_upscale=no_upscale)
        report_meta['resize_mode'] = 'cover'
        if note:
            report_meta['no_upscale_applied'] = True
        report_meta['note'] = _merge_notes(report_meta['note'], note)
        report_meta['output_width'] = resized.width
        report_meta['output_height'] = resized.height
        return resized, report_meta

    resized, note = _resize_contain(image, target_width, target_height, no_upscale=no_upscale)
    report_meta['resize_mode'] = 'contain'
    report_meta['note'] = _merge_notes(report_meta['note'], note)
    report_meta['no_upscale_applied'] = bool(note)
    report_meta['output_width'] = resized.width
    report_meta['output_height'] = resized.height
    return resized, report_meta


def _apply_manual_crop(image: Image.Image, crop_data: dict) -> Image.Image:
    """Recorta usando coordenadas normalizadas (0..1) sobre el tamaño original."""
    crop_x = crop_data.get('crop_x')
    crop_y = crop_data.get('crop_y')
    crop_w = crop_data.get('crop_w')
    crop_h = crop_data.get('crop_h')
    if crop_x is None or crop_y is None or crop_w is None or crop_h is None:
        return image

    left = int(round(crop_x * image.width))
    top = int(round(crop_y * image.height))
    right = int(round((crop_x + crop_w) * image.width))
    bottom = int(round((crop_y + crop_h) * image.height))

    left = max(0, min(left, image.width - 1))
    top = max(0, min(top, image.height - 1))
    right = max(left + 1, min(right, image.width))
    bottom = max(top + 1, min(bottom, image.height))
    return image.crop((left, top, right, bottom))


def _ensure_mode(image: Image.Image, keep_alpha: bool) -> Image.Image:
    """Garantiza modo de color apropiado según si se conserva transparencia."""
    if keep_alpha:
        if image.mode in ('RGBA', 'LA'):
            return image
        if image.mode == 'P':
            return image.convert('RGBA')
        return image.convert('RGBA')
    if image.mode == 'RGB':
        return image
    return image.convert('RGB')


def _merge_notes(existing: str, extra: str) -> str:
    if not extra:
        return existing
    if not existing:
        return extra
    return f"{existing} {extra}"


def _resize_contain(
    image: Image.Image,
    target_width: int,
    target_height: int,
    no_upscale: bool = True,
) -> Tuple[Image.Image, str]:
    """Encaja dentro del tamaño objetivo sin recortar; evita upscale si aplica."""
    ratio = min(target_width / float(image.width), target_height / float(image.height))
    note = ''
    if no_upscale and ratio > 1.0:
        ratio = 1.0
        note = NO_UPSCALE_NOTE

    if ratio == 1.0:
        return image, note

    width = max(1, int(image.width * ratio))
    height = max(1, int(image.height * ratio))
    return image.resize((width, height), Image.LANCZOS), note


def _resize_cover(
    image: Image.Image,
    target_width: int,
    target_height: int,
    no_upscale: bool = True,
) -> Tuple[Image.Image, str]:
    """Cubre el tamaño objetivo y recorta centrado; evita upscale si aplica."""
    ratio = max(target_width / float(image.width), target_height / float(image.height))
    note = ''
    if no_upscale and ratio > 1.0:
        ratio = 1.0
        note = NO_UPSCALE_NOTE

    if ratio == 1.0:
        resized = image
    else:
        resized = image.resize(
            (int(math.ceil(image.width * ratio)), int(math.ceil(image.height * ratio))),
            Image.LANCZOS,
        )

    if resized.width >= target_width and resized.height >= target_height:
        left = int((resized.width - target_width) / 2)
        top = int((resized.height - target_height) / 2)
        right = left + target_width
        bottom = top + target_height
        return resized.crop((left, top, right, bottom)), note

    # Si no alcanza el tamaño objetivo (sin upscale), se recorta al aspecto objetivo.
    target_aspect = target_width / float(target_height)
    input_aspect = resized.width / float(resized.height)
    if input_aspect > target_aspect:
        crop_width = int(round(resized.height * target_aspect))
        crop_height = resized.height
    else:
        crop_width = resized.width
        crop_height = int(round(resized.width / target_aspect))

    crop_width = min(crop_width, resized.width)
    crop_height = min(crop_height, resized.height)
    left = int((resized.width - crop_width) / 2)
    top = int((resized.height - crop_height) / 2)
    right = left + crop_width
    bottom = top + crop_height
    return resized.crop((left, top, right, bottom)), note


def _render_image(
    image: Image.Image,
    output_format: str,
    quality: int,
    keep_metadata: bool = False,
    metadata_payload: Optional[dict] = None,
) -> bytes:
    """Serializa la imagen al formato final, preservando metadatos si se permite."""
    buffer = BytesIO()
    if output_format == 'webp':
        save_kwargs = {'quality': quality, 'method': 6}
        if keep_metadata and metadata_payload:
            save_kwargs.update(metadata_payload)
        image.save(buffer, format='WEBP', **save_kwargs)
    elif output_format == 'jpg':
        save_kwargs = {'quality': quality, 'optimize': True}
        if keep_metadata and metadata_payload:
            save_kwargs.update(metadata_payload)
        image.save(buffer, format='JPEG', **save_kwargs)
    elif output_format == 'png':
        save_kwargs = {'optimize': True}
        if keep_metadata and metadata_payload:
            save_kwargs.update(metadata_payload)
        image.save(buffer, format='PNG', **save_kwargs)
    else:
        save_kwargs = {'quality': quality, 'method': 6}
        if keep_metadata and metadata_payload:
            save_kwargs.update(metadata_payload)
        image.save(buffer, format='WEBP', **save_kwargs)
    return buffer.getvalue()


def _resolve_format(preset: dict, defaults: dict) -> str:
    preset_format = preset.get('recommendedFormat')
    default_format = defaults.get('output', {}).get('recommendedFormat')
    candidate = (preset_format or default_format or 'webp').lower()
    return candidate if candidate in SUPPORTED_FORMATS else 'webp'


def _resolve_quality(preset: dict, defaults: dict) -> int:
    type_hint = preset.get('typeHint', 'photo')
    quality_map = defaults.get('quality', {})
    if isinstance(quality_map.get(type_hint), dict):
        return int(quality_map[type_hint].get('webp', 80))
    return int(quality_map.get('photo', {}).get('webp', 80))


def _resolve_resize_mode(preset: dict, defaults: dict) -> str:
    """Determina el modo de resize a partir del preset y defaults (cover/contain)."""
    def _normalize(mode: Optional[str]) -> Optional[str]:
        if not mode:
            return None
        value = str(mode).lower()
        if value in {'cover'}:
            return 'cover'
        if value in {'contain', 'fit', 'inside'}:
            return 'contain'
        return None

    preset_crop = _normalize(preset.get('crop', {}).get('mode'))
    preset_mode = _normalize(preset.get('resizeMode') or preset.get('cropMode'))
    default_crop = _normalize(defaults.get('crop', {}).get('mode'))

    for candidate in (preset_crop, preset_mode, default_crop):
        if candidate:
            return candidate

    if preset.get('width') and preset.get('height'):
        category = infer_category(preset.get('id', ''))
        return 'cover' if category == 'redes' else 'contain'

    return 'contain'


def _build_output_name(
    original_name: str,
    output_format: str,
    preset_id: str,
    presets_data: dict,
    job_file: JobFile,
) -> str:
    """Genera el nombre final basado en el patrón de naming y normalización."""
    naming = presets_data.get('naming', {})
    pattern = job_file.rename_pattern or naming.get('pattern') or "{name-normalized}.{ext}"
    normalize = naming.get('normalize', {})

    base = Path(original_name).stem
    normalized = _normalize_name(
        base,
        lowercase=job_file.normalize_lowercase if job_file.normalize_lowercase is not None else normalize.get('lowercase', True),
        remove_accents=job_file.normalize_remove_accents if job_file.normalize_remove_accents is not None else normalize.get('removeAccents', True),
        replace_spaces=job_file.normalize_replace_spaces or normalize.get('replaceSpacesWith', '-'),
        collapse_dashes=job_file.normalize_collapse_dashes if job_file.normalize_collapse_dashes is not None else normalize.get('collapseDashes', True),
    )

    return (
        pattern.replace("{preset}", preset_id or "")
        .replace("{ext}", output_format)
        .replace("{name-normalized}", normalized)
        .replace("{name}", base)
    )


def _build_output_base_name(
    original_name: str,
    preset_id: str,
    presets_data: dict,
    job_file: JobFile,
) -> str:
    """Genera un nombre base sin extensión para múltiples formatos/variantes."""
    naming = presets_data.get('naming', {})
    normalize = naming.get('normalize', {})

    base = Path(original_name).stem
    normalized = _normalize_name(
        base,
        lowercase=job_file.normalize_lowercase if job_file.normalize_lowercase is not None else normalize.get('lowercase', True),
        remove_accents=job_file.normalize_remove_accents if job_file.normalize_remove_accents is not None else normalize.get('removeAccents', True),
        replace_spaces=job_file.normalize_replace_spaces or normalize.get('replaceSpacesWith', '-'),
        collapse_dashes=job_file.normalize_collapse_dashes if job_file.normalize_collapse_dashes is not None else normalize.get('collapseDashes', True),
    )

    return f"{normalized}__{preset_id}" if preset_id else normalized


def _ensure_unique_name(name: str, used_names: set[str]) -> str:
    """Asegura unicidad del nombre dentro del ZIP agregando sufijos numéricos."""
    if name not in used_names:
        return name
    base = Path(name).stem
    suffix = Path(name).suffix
    counter = 2
    while True:
        candidate = f"{base}-{counter}{suffix}"
        if candidate not in used_names:
            return candidate
        counter += 1


def _build_report_row(job_file: JobFile, meta: dict) -> dict:
    """Consolida datos del archivo procesado para el reporte TXT/CSV."""
    reduction = None
    if job_file.output_size and job_file.original_size > 0:
        reduction = round((1 - (job_file.output_size / job_file.original_size)) * 100, 2)

    final_format = None
    if job_file.output_name and '.' in job_file.output_name:
        final_format = job_file.output_name.rsplit('.', 1)[-1].lower()

    final_aspect = ''
    if meta.get('output_width') and meta.get('output_height'):
        final_aspect = _closest_aspect_label(meta.get('output_width'), meta.get('output_height'))

    return {
        'original_name': job_file.original_name,
        'original_size': job_file.original_size,
        'output_name': job_file.output_name,
        'output_size': job_file.output_size,
        'reduction_percent': reduction,
        'final_format': final_format,
        'status': job_file.status,
        'error_message': job_file.error_message,
        'input_width': meta.get('input_width'),
        'input_height': meta.get('input_height'),
        'output_width': meta.get('output_width'),
        'output_height': meta.get('output_height'),
        'resize_mode': meta.get('resize_mode'),
        'no_upscale_applied': meta.get('no_upscale_applied', False),
        'note': meta.get('note', ''),
        'analysis_type': job_file.analysis_type,
        'has_transparency': job_file.has_transparency,
        'orientation': job_file.orientation,
        'aspect_label': job_file.aspect_label,
        'aspect_final': final_aspect,
        'metadata_tags': job_file.metadata_tags,
        'keep_metadata': job_file.keep_metadata,
        'recommended_preset_label': job_file.recommended_preset_label,
        'recommended_formats': job_file.recommended_formats,
        'recommended_quality': job_file.recommended_quality,
        'recommended_crop_mode': job_file.recommended_crop_mode,
        'recommended_crop_reason': job_file.recommended_crop_reason,
        'recommended_notes': job_file.recommended_notes,
        'applied_preset_label': meta.get('applied_preset_label'),
        'applied_format': meta.get('applied_format'),
        'applied_quality': meta.get('applied_quality'),
        'applied_rename': meta.get('applied_rename'),
        'metadata_action': meta.get('metadata_action'),
        'transparency_action': meta.get('transparency_action'),
        'generated_outputs': meta.get('generated_outputs'),
        'cropped': meta.get('cropped'),
        'metadata_removed': meta.get('metadata_removed'),
    }


def _process_job_file(
    job_file: JobFile,
    job: Job,
    target_size: Tuple[Optional[int], Optional[int]],
    resize_mode: str,
    output_format: str,
    quality: int,
    no_upscale: bool = True,
    presets_data: Optional[dict] = None,
    defaults: Optional[dict] = None,
    used_names: Optional[set[str]] = None,
) -> Tuple[bytes, str, dict]:
    """Procesa un archivo individual y devuelve bytes, nombre y meta de reporte.

    Aplica análisis, overrides, recorte/resize, formatos múltiples y variantes 1x/2x.
    """
    with Image.open(job_file.original_file.path) as image:
        max_mp = getattr(settings, 'MAX_IMAGE_MP', 100)
        if (image.width * image.height) > (max_mp * 1_000_000):
            raise ValueError('Imagen demasiado grande (MP). Reduce tamaño antes.')
        analysis = _analyze_image(image)
        _save_analysis(job_file, analysis)
        if presets_data is not None and defaults is not None:
            _save_recommendation(job_file, job, analysis, presets_data, defaults)
            effective = _resolve_effective_settings(
                job_file,
                job,
                analysis,
                presets_data,
                defaults,
                output_format,
                quality,
            )
        else:
            effective = {
                'preset_id': job.preset,
                'preset_label': '',
                'target_size': target_size,
                'resize_mode': resize_mode,
                'output_format': output_format,
                'quality': quality,
                'keep_alpha': analysis['has_transparency'],
                'note': '',
                'transparency_action': '',
            }
        metadata_payload = _extract_metadata_payload(image, keep_metadata=job_file.keep_metadata)
        output_variants = []
        output_bytes = b''
        output_name = ''
        report_meta = {}
        notes = effective.get('note', '')

        presets_data = presets_data or {}
        base_target_width, base_target_height = effective['target_size']
        density_scale = defaults.get('resize', {}).get('density', {}).get('scaleFactor', 1.33) if defaults else 1.33
        generate_2x = effective.get('generate_2x', False)
        generate_sharpened = effective.get('generate_sharpened', False)

        if generate_2x and generate_sharpened:
            generate_sharpened = False
            notes = _merge_notes(notes, 'Se desactivó “Más nítido” porque 2x está activo.')

        if generate_2x:
            scales = [(1.0, '1x'), (2.0, '2x')]
        elif generate_sharpened:
            scales = [(float(density_scale), '1x')]
        else:
            scales = [(1.0, '1x')]

        primary_format = effective.get('primary_format') or output_format
        formats = effective.get('output_formats') or [primary_format]

        # Genera variantes por formato y escala respetando "sin upscale".
        for fmt in formats:
            fmt_quality = _resolve_effective_quality(job_file, fmt, analysis, defaults, quality)
            for scale_value, scale_label in scales:
                target_width = None
                target_height = None
                if base_target_width and base_target_height:
                    target_width = int(round(base_target_width * scale_value))
                    target_height = int(round(base_target_height * scale_value))

                variant_effective = {
                    'output_format': fmt,
                    'note': '',
                    'transparency_action': '',
                }
                variant_image = _apply_transparency_rules(
                    image.copy(),
                    analysis,
                    variant_effective,
                    job_file.keep_transparency,
                )
                keep_alpha = analysis.get('has_transparency', False) and fmt in {'webp', 'png'} and job_file.keep_transparency
                resized, variant_meta = _prepare_image(
                    variant_image,
                    (target_width, target_height),
                    effective['resize_mode'],
                    no_upscale=no_upscale,
                    crop_data=_extract_crop_data(job_file),
                    keep_alpha=keep_alpha,
                )

                if scale_label == '2x' and target_width and target_height:
                    if resized.width < target_width or resized.height < target_height:
                        notes = _merge_notes(
                            notes,
                            'No se generó 2x porque el original no alcanza el tamaño requerido.',
                        )
                        continue

                if generate_sharpened and target_width and target_height:
                    if resized.width < target_width or resized.height < target_height:
                        notes = _merge_notes(
                            notes,
                            '“Más nítido” se limitó al máximo posible por tamaño del original.',
                        )

                if generate_2x:
                    base_name = _build_output_base_name(
                        job_file.original_name,
                        effective['preset_id'],
                        presets_data,
                        job_file,
                    )
                    if scale_label == '2x':
                        name_candidate = f"{base_name}__2x.{fmt}"
                    else:
                        name_candidate = f"{base_name}.{fmt}"
                else:
                    name_candidate = _build_output_name(
                        job_file.original_name,
                        fmt,
                        effective['preset_id'],
                        presets_data,
                        job_file,
                    )

                if used_names is not None:
                    name_candidate = _ensure_unique_name(name_candidate, used_names)
                    used_names.add(name_candidate)

                variant_bytes = _render_image(
                    resized,
                    fmt,
                    fmt_quality,
                    keep_metadata=job_file.keep_metadata,
                    metadata_payload=metadata_payload,
                )

                is_primary = scale_label == '1x' and fmt == primary_format and not output_name

                if not is_primary:
                    _save_extra_output(job_file, name_candidate, variant_bytes)

                output_variants.append(
                    {
                        'name': name_candidate,
                        'size': len(variant_bytes),
                        'format': fmt,
                        'scale': scale_label,
                        'width': resized.width,
                        'height': resized.height,
                        'storage_name': f"outputs/{name_candidate}",
                    }
                )

                if is_primary:
                    output_name = name_candidate
                    output_bytes = variant_bytes
                    report_meta = variant_meta
                    report_meta['output_width'] = resized.width
                    report_meta['output_height'] = resized.height
                    report_meta['note'] = _merge_notes(report_meta.get('note', ''), variant_effective.get('note', ''))
                    report_meta['note'] = _merge_notes(report_meta.get('note', ''), notes)
                    report_meta['transparency_action'] = variant_effective.get('transparency_action', '')

        report_meta.update(
            {
                'applied_preset_label': effective['preset_label'],
                'applied_format': primary_format,
                'applied_quality': _resolve_effective_quality(job_file, primary_format, analysis, defaults, quality),
                'applied_rename': output_name,
                'metadata_action': 'Conservados' if job_file.keep_metadata else 'Eliminados',
                'transparency_action': report_meta.get('transparency_action', ''),
                'generated_outputs': output_variants,
                'cropped': report_meta.get('resize_mode') == 'cover',
                'metadata_removed': not job_file.keep_metadata,
            }
        )

        job_file.output_formats = formats
        job_file.output_variants = output_variants
        job_file.generate_2x = generate_2x
        job_file.generate_sharpened = generate_sharpened
        job_file.output_format = primary_format
        job_file.cropped = report_meta.get('resize_mode') == 'cover'
        job_file.metadata_removed = not job_file.keep_metadata
        job_file.save(
            update_fields=[
                'output_formats',
                'output_variants',
                'generate_2x',
                'generate_sharpened',
                'output_format',
                'cropped',
                'metadata_removed',
            ],
        )
    return output_bytes, output_name, report_meta


def _save_job_file_output(
    job_file: JobFile,
    output_name: str,
    output_bytes: bytes,
    output_width: Optional[int] = None,
    output_height: Optional[int] = None,
) -> None:
    job_file.output_size = len(output_bytes)
    job_file.output_width = output_width
    job_file.output_height = output_height
    saved_name = job_file.output_file.save(output_name, ContentFile(output_bytes), save=False)
    job_file.output_name = Path(saved_name).name if saved_name else output_name
    job_file.status = JobFile.Status.DONE
    job_file.error_message = ''
    job_file.save()


def _save_extra_output(job_file: JobFile, output_name: str, output_bytes: bytes) -> None:
    storage = job_file.output_file.storage
    storage.save(f"outputs/{output_name}", ContentFile(output_bytes))


def _extract_crop_data(job_file: JobFile) -> Optional[dict]:
    if not job_file.crop_enabled:
        return None
    return {
        'crop_mode': job_file.crop_mode,
        'crop_x': job_file.crop_x,
        'crop_y': job_file.crop_y,
        'crop_w': job_file.crop_w,
        'crop_h': job_file.crop_h,
    }


def _derive_report_meta(job_file: JobFile, preset: dict, defaults: dict) -> dict:
    input_width = job_file.original_width
    input_height = job_file.original_height
    output_width = job_file.output_width
    output_height = job_file.output_height

    if not input_width or not input_height:
        try:
            if job_file.original_file and job_file.original_file.path:
                with Image.open(job_file.original_file.path) as image:
                    input_width, input_height = image.size
        except Exception:
            pass

    if not output_width or not output_height:
        try:
            if job_file.output_file and job_file.output_file.path:
                with Image.open(job_file.output_file.path) as image:
                    output_width, output_height = image.size
        except Exception:
            pass

    resize_mode = 'manual' if job_file.crop_mode == 'manual' else _resolve_resize_mode(preset, defaults)

    return {
        'input_width': input_width,
        'input_height': input_height,
        'output_width': output_width,
        'output_height': output_height,
        'resize_mode': resize_mode,
        'no_upscale_applied': False,
        'note': '',
        'applied_preset_label': job_file.recommended_preset_label or preset.get('label', ''),
        'applied_format': job_file.output_format or (job_file.output_name.rsplit('.', 1)[-1] if job_file.output_name else ''),
        'applied_quality': job_file.quality_webp or job_file.quality_jpg,
        'applied_rename': job_file.output_name or '',
        'metadata_action': 'Conservados' if job_file.keep_metadata else 'Eliminados',
        'transparency_action': '',
        'generated_outputs': job_file.output_variants,
        'cropped': job_file.cropped,
        'metadata_removed': job_file.metadata_removed if job_file.metadata_removed is not None else (not job_file.keep_metadata),
    }


def _collect_report_rows(
    job: Job,
    preset: dict,
    defaults: dict,
    overrides: Optional[dict[int, dict]] = None,
) -> list[dict]:
    overrides = overrides or {}
    rows = []
    for job_file in job.files.all():
        meta = overrides.get(job_file.id) or _derive_report_meta(job_file, preset, defaults)
        rows.append(_build_report_row(job_file, meta))
    return rows


def _analyze_image(image: Image.Image) -> dict:
    """Extrae métricas básicas (dimensiones, orientación, transparencia y metadatos)."""
    width, height = image.size
    orientation = _orientation_from_size(width, height)
    aspect_label = _closest_aspect_label(width, height)
    has_transparency = _detect_transparency(image)
    analysis_type = _infer_type(image, has_transparency)
    metadata_tags = _detect_metadata_tags(image)

    return {
        'original_width': width,
        'original_height': height,
        'orientation': orientation,
        'aspect_label': aspect_label,
        'has_transparency': has_transparency,
        'analysis_type': analysis_type,
        'metadata_tags': metadata_tags,
    }


def _save_analysis(job_file: JobFile, analysis: dict) -> None:
    """Persiste el análisis calculado en el JobFile."""
    job_file.original_width = analysis['original_width']
    job_file.original_height = analysis['original_height']
    job_file.orientation = analysis['orientation']
    job_file.aspect_label = analysis['aspect_label']
    job_file.has_transparency = analysis['has_transparency']
    job_file.analysis_type = analysis['analysis_type']
    job_file.metadata_tags = analysis['metadata_tags']
    job_file.save(
        update_fields=[
            'original_width',
            'original_height',
            'orientation',
            'aspect_label',
            'has_transparency',
            'analysis_type',
            'metadata_tags',
        ],
    )


def _save_recommendation(
    job_file: JobFile,
    job: Job,
    analysis: dict,
    presets_data: dict,
    defaults: dict,
) -> None:
    """Calcula y guarda recomendaciones por archivo basadas en el análisis."""
    recommendation = _build_recommendation(job, analysis, presets_data, defaults)
    job_file.recommended_preset_id = recommendation['recommended_preset_id']
    job_file.recommended_preset_label = recommendation['recommended_preset_label']
    job_file.recommended_formats = recommendation['recommended_formats']
    job_file.recommended_quality = recommendation['recommended_quality']
    job_file.recommended_crop_mode = recommendation['recommended_crop_mode']
    job_file.recommended_crop_reason = recommendation['recommended_crop_reason']
    job_file.recommended_notes = recommendation['recommended_notes']
    job_file.save(
        update_fields=[
            'recommended_preset_id',
            'recommended_preset_label',
            'recommended_formats',
            'recommended_quality',
            'recommended_crop_mode',
            'recommended_crop_reason',
            'recommended_notes',
        ],
    )


def _orientation_from_size(width: int, height: int) -> str:
    if width > height:
        return 'HORIZONTAL'
    if height > width:
        return 'VERTICAL'
    return 'CUADRADA'


def _closest_aspect_label(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return ''
    ratio = width / float(height)
    candidates = {
        '16:9': 16 / 9,
        '4:5': 4 / 5,
        '1:1': 1,
        '9:16': 9 / 16,
        '4:3': 4 / 3,
        '3:2': 3 / 2,
        '21:9': 21 / 9,
    }
    return min(candidates.items(), key=lambda item: abs(item[1] - ratio))[0]


def _detect_transparency(image: Image.Image) -> bool:
    if image.mode in ('RGBA', 'LA'):
        return True
    if image.mode == 'P':
        return 'transparency' in image.info
    return 'transparency' in image.info


def _infer_type(image: Image.Image, has_transparency: bool) -> str:
    if has_transparency:
        return 'ui'
    if image.mode in ('P', '1'):
        return 'ui'
    try:
        if image.getcolors(maxcolors=256) is not None:
            return 'ui'
    except Exception:
        pass
    return 'photo'


def _detect_metadata_tags(image: Image.Image) -> list[str]:
    tags = []
    try:
        exif = image.getexif()
        if exif and len(exif):
            tags.append('EXIF')
    except Exception:
        pass
    if image.info.get('icc_profile'):
        tags.append('ICC')
    if image.info.get('xmp') or image.info.get('XML:com.adobe.xmp'):
        tags.append('XMP')
    return tags


def _extract_metadata_payload(image: Image.Image, keep_metadata: bool) -> dict:
    if not keep_metadata:
        return {}
    payload = {}
    exif = image.info.get('exif')
    if exif:
        payload['exif'] = exif
    icc = image.info.get('icc_profile')
    if icc:
        payload['icc_profile'] = icc
    xmp = image.info.get('xmp') or image.info.get('XML:com.adobe.xmp')
    if xmp:
        payload['xmp'] = xmp
    return payload


def _build_recommendation(job: Job, analysis: dict, presets_data: dict, defaults: dict) -> dict:
    """Combina formato, preset y recorte sugeridos para UI y reporte."""
    formats, quality, notes = _recommend_formats_and_quality(analysis, defaults)
    preset = _recommend_preset(job, analysis, presets_data)
    crop_mode, crop_reason = _recommend_crop_mode(analysis, preset)

    return {
        'recommended_preset_id': preset.get('id', '') if preset else '',
        'recommended_preset_label': preset.get('label', '') if preset else '',
        'recommended_formats': formats,
        'recommended_quality': quality,
        'recommended_crop_mode': crop_mode,
        'recommended_crop_reason': crop_reason,
        'recommended_notes': notes,
    }


def _recommend_formats_and_quality(analysis: dict, defaults: dict) -> tuple[list[str], dict, str]:
    has_transparency = analysis.get('has_transparency')
    analysis_type = analysis.get('analysis_type')
    quality_defaults = defaults.get('quality', {})
    notes = ''

    if analysis_type == 'photo' and not has_transparency:
        formats = ['avif', 'webp']
        quality = quality_defaults.get('photo', {})
        notes = 'Foto sin transparencia: se sugiere AVIF/WebP.'
        return formats, quality, notes

    formats = ['webp']
    if has_transparency:
        formats.append('png')
        notes = 'Imagen con transparencia: se sugiere WebP/PNG.'
    else:
        notes = 'Gráfica UI: se sugiere WebP.'

    quality = quality_defaults.get('ui', {})
    return formats, quality, notes


def _recommend_preset(job: Job, analysis: dict, presets_data: dict) -> dict:
    presets = presets_data.get('presets', [])
    if not presets:
        return {}

    job_preset = get_preset(job.preset) if job.preset else None
    preferred_category = None
    if job_preset:
        preferred_category = job_preset.get('category') or infer_category(job_preset.get('id', ''))

    filtered = presets
    if preferred_category:
        same_category = [
            preset
            for preset in presets
            if (preset.get('category') or infer_category(preset.get('id', ''))) == preferred_category
        ]
        if same_category:
            filtered = same_category

    original_width = analysis.get('original_width') or 0
    original_height = analysis.get('original_height') or 0
    if original_width <= 0 or original_height <= 0:
        return job_preset or filtered[0]

    def score(preset: dict) -> float:
        width = preset.get('width')
        height = preset.get('height')
        if not width or not height:
            return 9999.0
        aspect_target = width / float(height)
        aspect_src = original_width / float(original_height)
        aspect_diff = abs(aspect_target - aspect_src)
        size_diff = (
            abs(width - original_width) / float(original_width)
            + abs(height - original_height) / float(original_height)
        )
        upscale_penalty = 0.0
        if width > original_width or height > original_height:
            upscale_penalty = 2.0 + (
                max(width - original_width, 0) / float(width)
                + max(height - original_height, 0) / float(height)
            )
        return aspect_diff * 2.0 + size_diff + upscale_penalty * 3.0

    return min(filtered, key=score)


def _recommend_crop_mode(analysis: dict, preset: Optional[dict]) -> tuple[str, str]:
    if not preset:
        return 'contain', ''

    width = preset.get('width')
    height = preset.get('height')
    if not width or not height:
        return 'contain', ''

    original_orientation = analysis.get('orientation')
    target_ratio = width / float(height)
    if original_orientation == 'HORIZONTAL' and target_ratio <= 1:
        return 'cover', 'Se recomienda recorte para ajustar un formato vertical/cuadrado.'

    return 'contain', ''


def _build_zip(job: Job, preset: dict, report_rows: list[dict], output_format: str) -> Optional[str]:
    """Empaqueta outputs y reportes en un ZIP listo para descarga."""
    if not job.files.exists():
        return None

    zips_dir = Path(settings.MEDIA_ROOT) / 'zips'
    zips_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"job_{job.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.zip"
    zip_path = zips_dir / zip_name

    report_data = {
        'job_id': job.id,
        'preset_id': preset.get('id'),
        'preset_label': preset.get('label'),
        'generated_at': timezone.now().isoformat(),
        'output_format': output_format,
        'files': report_rows,
        'total_files': job.total_files,
        'processed_files': job.processed_files,
        'status': job.status,
        'finished_at': job.finished_at.isoformat() if job.finished_at else None,
    }

    with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zip_file:
        for job_file in job.files.all():
            added = set()
            if job_file.output_variants:
                for variant in job_file.output_variants:
                    if not isinstance(variant, dict):
                        continue
                    name = variant.get('name')
                    storage_name = variant.get('storage_name')
                    if not name or not storage_name or name in added:
                        continue
                    try:
                        path = job_file.output_file.storage.path(storage_name)
                    except Exception:
                        path = None
                    if path and os.path.exists(path):
                        zip_file.write(path, arcname=name)
                        added.add(name)
            if job_file.output_file and job_file.output_file.name and job_file.output_name not in added:
                zip_file.write(job_file.output_file.path, arcname=job_file.output_name)
        zip_file.writestr('reporte.txt', _build_report_txt(report_data))
        zip_file.writestr('reporte.csv', _build_report_csv(report_data))
        # Se incluye TXT/CSV como reporte principal del ZIP.

    return os.path.relpath(zip_path, settings.MEDIA_ROOT)


def _format_bytes(size: Optional[int]) -> str:
    if size is None:
        return '-'
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _format_dims(width: Optional[int], height: Optional[int]) -> str:
    if not width or not height:
        return '-'
    return f"{width}x{height}"


def _status_label(value: Optional[str]) -> str:
    if not value:
        return '-'
    mapping = {
        'PENDING': 'En espera',
        'PROCESSING': 'En proceso',
        'PAUSED': 'Pausado',
        'CANCELED': 'Cancelado',
        'DONE': 'Completado',
        'FAILED': 'Fallido',
    }
    return mapping.get(str(value), str(value))


def _yes_no(value: Optional[bool]) -> str:
    if value is True:
        return 'Sí'
    if value is False:
        return 'No'
    return '-'


def _translate_mode(value: Optional[str]) -> str:
    if not value:
        return '-'
    mapping = {
        'cover': 'recorte',
        'contain': 'ajustar',
        'manual': 'manual',
    }
    return mapping.get(str(value), str(value))


def _translate_type(value: Optional[str]) -> str:
    if not value:
        return '-'
    mapping = {
        'photo': 'Foto',
        'ui': 'UI',
    }
    return mapping.get(str(value), str(value))


def _report_table_data(report_data: dict) -> tuple[list[str], list[list[str]]]:
    rows = [
        [
            row.get('original_name') or '-',
            _format_dims(row.get('input_width'), row.get('input_height')),
            _format_bytes(row.get('original_size')),
            _format_dims(row.get('output_width'), row.get('output_height')),
            _format_bytes(row.get('output_size')),
            f"{row.get('reduction_percent')}%" if row.get('reduction_percent') is not None else '-',
            _translate_mode(row.get('resize_mode')),
            _yes_no(row.get('cropped')),
            _yes_no(row.get('metadata_removed')),
            _translate_type(row.get('analysis_type')),
            _yes_no(row.get('has_transparency')),
            row.get('orientation') or '-',
            row.get('aspect_label') or '-',
            row.get('aspect_final') or '-',
            ', '.join(row.get('metadata_tags') or []) or '-',
            'Conservados' if row.get('keep_metadata') else 'Eliminados',
            row.get('recommended_preset_label') or '-',
            ', '.join(row.get('recommended_formats') or []) or '-',
            _format_quality(row.get('recommended_quality') or {}),
            _translate_mode(row.get('recommended_crop_mode')),
            row.get('recommended_crop_reason') or '-',
            row.get('applied_preset_label') or '-',
            row.get('applied_format') or '-',
            str(row.get('applied_quality')) if row.get('applied_quality') else '-',
            row.get('applied_rename') or '-',
            _format_outputs(row.get('generated_outputs')),
            row.get('metadata_action') or '-',
            row.get('transparency_action') or '-',
            _status_label(row.get('status')),
            row.get('error_message') or row.get('note') or '-',
        ]
        for row in report_data.get('files', [])
    ]

    columns = [
        "nombre_original",
        "dims_original",
        "peso_original",
        "dims_final",
        "peso_final",
        "ahorro%",
        "modo",
        "recorte",
        "metadatos_eliminados",
        "tipo",
        "transparencia",
        "orientacion",
        "aspect",
        "aspect_final",
        "metadatos",
        "metadatos_accion",
        "preset_sugerido",
        "formatos_sugeridos",
        "calidad_sugerida",
        "recorte_sugerido",
        "recorte_razon",
        "preset_final",
        "formato_final",
        "calidad_final",
        "renombre",
        "salidas_generadas",
        "metadatos_final",
        "transparencia_final",
        "estado",
        "error",
    ]
    return columns, rows


def _build_report_txt(report_data: dict) -> str:
    """Genera un reporte legible en texto con detalle por archivo y resumen final."""
    header_lines = [
        f"Reporte del trabajo #{report_data.get('job_id')}",
        f"Preset: {report_data.get('preset_label')} ({report_data.get('preset_id')})",
        f"Fecha: {report_data.get('generated_at')}",
        f"Estado final: {_status_label(report_data.get('status'))}",
        f"Archivos: {report_data.get('processed_files')}/{report_data.get('total_files')}",
        f"Finalizado: {report_data.get('finished_at') or '-'}",
        "",
    ]
    columns, rows = _report_table_data(report_data)

    widths = [len(col) for col in columns]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(str(value)))

    def _fmt_row(values: list[str]) -> str:
        return " | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(values))

    lines = header_lines[:]
    lines.append(_fmt_row(columns))
    lines.append("-+-".join('-' * width for width in widths))
    for row in rows:
        lines.append(_fmt_row(row))

    total_original = sum((row.get('original_size') or 0) for row in report_data.get('files', []))
    total_output = sum((row.get('output_size') or 0) for row in report_data.get('files', []))
    savings_mb = max(total_original - total_output, 0) / (1024 * 1024) if total_original else 0
    avg_reduction = None
    reductions = [row.get('reduction_percent') for row in report_data.get('files', []) if row.get('reduction_percent') is not None]
    if reductions:
        avg_reduction = round(sum(reductions) / len(reductions), 2)

    lines.append("")
    lines.append("Resumen")
    lines.append(f"Ahorro total: {savings_mb:.2f} MB")
    lines.append(f"Reducción promedio: {avg_reduction if avg_reduction is not None else '-'}%")

    return "\n".join(lines)


def _build_report_csv(report_data: dict) -> str:
    """Genera un CSV de reporte para análisis en hojas de cálculo."""
    import csv
    output = StringIO()
    writer = csv.writer(output, lineterminator='\n')
    columns, rows = _report_table_data(report_data)
    writer.writerow(columns)
    writer.writerows(rows)
    return output.getvalue()


def _format_quality(value: dict) -> str:
    if not value:
        return '-'
    return ', '.join(f"{key}={value[key]}" for key in sorted(value.keys()))


def _format_outputs(outputs: Optional[list[dict]]) -> str:
    if not outputs:
        return '-'
    parts = []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        name = item.get('name') or ''
        fmt = item.get('format') or ''
        scale = item.get('scale') or ''
        dims = _format_dims(item.get('width'), item.get('height'))
        size = _format_bytes(item.get('size'))
        label = f"{fmt} {scale}".strip()
        if dims != '-':
            label = f"{label} {dims}".strip()
        if size != '-':
            label = f"{label} {size}".strip()
        if name:
            label = f"{label} [{name}]"
        parts.append(label)
    return '; '.join(parts) if parts else '-'


def _normalize_name(
    value: str,
    lowercase: bool = True,
    remove_accents: bool = True,
    replace_spaces: str = '-',
    collapse_dashes: bool = True,
) -> str:
    text = value
    if remove_accents:
        text = ''.join(
            char for char in unicodedata.normalize('NFD', text) if unicodedata.category(char) != 'Mn'
        )
    if lowercase:
        text = text.lower()
    if replace_spaces is not None:
        text = text.replace(' ', replace_spaces)
    if collapse_dashes:
        while '--' in text:
            text = text.replace('--', '-')
    return text.strip(replace_spaces or '-')


def _resolve_effective_settings(
    job_file: JobFile,
    job: Job,
    analysis: dict,
    presets_data: dict,
    defaults: dict,
    fallback_format: str,
    fallback_quality: int,
) -> dict:
    """Combina overrides, recomendaciones y defaults para un archivo.

    Define preset, formato, calidad, transparencias y flags de salida efectiva.
    """
    preset = _resolve_effective_preset(job_file, job, presets_data)
    resize_mode = _resolve_resize_mode(preset, defaults) if preset else 'contain'
    target_size = (preset.get('width'), preset.get('height')) if preset else (None, None)
    output_formats = _resolve_effective_formats(job_file, fallback_format)
    primary_format = _resolve_primary_format(job_file, output_formats, fallback_format)
    quality = _resolve_effective_quality(job_file, primary_format, analysis, defaults, fallback_quality)
    keep_alpha = (
        analysis.get('has_transparency', False)
        and primary_format in {'webp', 'png'}
        and job_file.keep_transparency
    )
    # Respeta el modo del preset; solo forza cover si el recorte manual está activo.
    if job_file.crop_enabled:
        resize_mode = 'cover'
    note = ''
    if job_file.crop_enabled:
        note = _merge_notes(note, 'Recorte activado.')

    return {
        'preset_id': preset.get('id', '') if preset else '',
        'preset_label': preset.get('label', '') if preset else '',
        'target_size': target_size,
        'resize_mode': resize_mode,
        'output_formats': output_formats,
        'primary_format': primary_format,
        'quality': quality,
        'keep_alpha': keep_alpha,
        'note': note,
        'transparency_action': '',
        'generate_2x': job_file.generate_2x,
        'generate_sharpened': job_file.generate_sharpened,
    }


def _resolve_effective_preset(job_file: JobFile, job: Job, presets_data: dict) -> Optional[dict]:
    if job_file.selected_preset_id:
        return get_preset(job_file.selected_preset_id)
    if job.preset:
        preset = get_preset(job.preset)
        if preset:
            return preset
    if job_file.recommended_preset_id:
        return get_preset(job_file.recommended_preset_id)
    presets = presets_data.get('presets', [])
    return presets[0] if presets else None


def _resolve_effective_format(job_file: JobFile, fallback_format: str) -> str:
    if job_file.output_format:
        return job_file.output_format
    recommended = (job_file.recommended_formats or [])
    for fmt in recommended:
        if fmt in SUPPORTED_FORMATS:
            return fmt
    return fallback_format if fallback_format in SUPPORTED_FORMATS else 'webp'


def _resolve_effective_formats(job_file: JobFile, fallback_format: str) -> list[str]:
    if job_file.output_formats:
        formats = [fmt for fmt in job_file.output_formats if fmt in SUPPORTED_FORMATS]
        if formats:
            return formats
    if job_file.output_format and job_file.output_format in SUPPORTED_FORMATS:
        return [job_file.output_format]
    recommended = [fmt for fmt in (job_file.recommended_formats or []) if fmt in SUPPORTED_FORMATS]
    if recommended:
        return recommended
    return [fallback_format if fallback_format in SUPPORTED_FORMATS else 'webp']


def _resolve_primary_format(
    job_file: JobFile,
    formats: list[str],
    fallback_format: str,
) -> str:
    if job_file.output_format and job_file.output_format in formats:
        return job_file.output_format
    if formats:
        return formats[0]
    return fallback_format if fallback_format in SUPPORTED_FORMATS else 'webp'


def _resolve_effective_quality(
    job_file: JobFile,
    output_format: str,
    analysis: dict,
    defaults: dict,
    fallback_quality: int,
) -> int:
    if output_format == 'webp':
        if job_file.quality_webp:
            return job_file.quality_webp
        quality_map = defaults.get('quality', {})
        hint = analysis.get('analysis_type', 'photo')
        return int(quality_map.get(hint, {}).get('webp', fallback_quality))
    if output_format == 'jpg':
        if job_file.quality_jpg:
            return job_file.quality_jpg
        quality_map = defaults.get('quality', {})
        return int(quality_map.get('photo', {}).get('jpg', 82))
    if output_format == 'png':
        return 0
    return fallback_quality


def _apply_transparency_rules(
    image: Image.Image,
    analysis: dict,
    effective: dict,
    keep_transparency: bool,
) -> Image.Image:
    """Aplica reglas de transparencia según formato final y configuración."""
    if not analysis.get('has_transparency'):
        return image

    if not keep_transparency:
        effective['note'] = _merge_notes(effective.get('note', ''), 'Transparencia eliminada por configuración.')
        effective['transparency_action'] = 'Transparencia eliminada'
        return image.convert('RGB')

    if effective['output_format'] == 'jpg':
        if image.mode == 'P':
            image = image.convert('RGBA')
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
        effective['note'] = _merge_notes(
            effective.get('note', ''),
            'Se perdió transparencia al exportar en JPG.',
        )
        effective['transparency_action'] = 'Transparencia perdida (JPG)'
        return background

    return image
