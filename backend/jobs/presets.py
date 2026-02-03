from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import PresetCustom

_PRESETS_PATH = Path(__file__).resolve().parent / 'image-presets.json'
_CACHE: Dict[str, object] = {'mtime': None, 'data': None}

_CATEGORY_ORDER = ['web', 'redes', 'ecommerce']
_WEB_PREFIXES = ('hero-', 'content-', 'thumb-', 'portrait-', 'story', 'square', 'panorama', 'logo-')
_SOCIAL_PREFIXES = ('ig-', 'fb-', 'x-', 'thr-', 'li-', 'tt-', 'yt-', 'pin-', 'sc-')


def load_presets() -> dict:
    """Carga el JSON base de presets con caché por mtime."""
    if not _PRESETS_PATH.exists():
        raise FileNotFoundError(f'No existe {_PRESETS_PATH}')

    mtime = _PRESETS_PATH.stat().st_mtime
    if _CACHE['data'] is None or _CACHE['mtime'] != mtime:
        _CACHE['data'] = json.loads(_PRESETS_PATH.read_text(encoding='utf-8'))
        _CACHE['mtime'] = mtime
    return _CACHE['data']  # type: ignore[return-value]


def get_preset(preset_id: str) -> Optional[dict]:
    """Busca un preset por id, priorizando personalizados."""
    custom = PresetCustom.objects.filter(preset_id=preset_id).first()
    if custom:
        return _serialize_custom(custom)
    data = load_presets()
    for preset in data.get('presets', []):
        if preset.get('id') == preset_id:
            return preset
    return None


def list_presets_response() -> dict:
    """Une presets base y personalizados en un payload ordenado por categoría."""
    data = load_presets()
    grouped: Dict[str, List[dict]] = {key: [] for key in _CATEGORY_ORDER}

    for preset in data.get('presets', []):
        category = preset.get('category') or _infer_category(preset.get('id', ''))
        entry = {
            'id': preset.get('id'),
            'label': preset.get('label'),
            'category': category,
            'width': preset.get('width'),
            'height': preset.get('height'),
            'aspect': preset.get('aspect'),
            'typeHint': preset.get('typeHint'),
            'recommendedFormat': preset.get('recommendedFormat'),
            'density': preset.get('density'),
            'source': 'base',
        }
        grouped.setdefault(category, []).append(entry)

    for custom in PresetCustom.objects.all():
        entry = _serialize_custom(custom)
        grouped.setdefault(entry.get('category') or 'ecommerce', []).append(entry)

    ordered_presets: List[dict] = []
    for category in _CATEGORY_ORDER:
        ordered_presets.extend(grouped.get(category, []))

    for category, entries in grouped.items():
        if category in _CATEGORY_ORDER:
            continue
        ordered_presets.extend(entries)

    return {
        'version': data.get('version', 1),
        'naming': data.get('naming', {}),
        'defaults': data.get('defaults', {}),
        'presets': ordered_presets,
    }


def infer_category(preset_id: str) -> str:
    """Categoriza un preset por prefijo para ordenar y sugerir en UI."""
    return _infer_category(preset_id)


def _infer_category(preset_id: str) -> str:
    """Regla interna de categorización por prefijos conocidos."""
    for prefix in _WEB_PREFIXES:
        if preset_id.startswith(prefix):
            return 'web'
    for prefix in _SOCIAL_PREFIXES:
        if preset_id.startswith(prefix):
            return 'redes'
    return 'ecommerce'


def _serialize_custom(custom: PresetCustom) -> dict:
    """Convierte un preset personalizado al esquema de respuesta estándar."""
    return {
        'id': custom.preset_id,
        'label': custom.label,
        'category': custom.category,
        'width': custom.width,
        'height': custom.height,
        'aspect': custom.aspect,
        'typeHint': custom.type_hint,
        'recommendedFormat': custom.recommended_format or None,
        'density': custom.density,
        'source': 'custom',
    }
