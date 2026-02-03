"""
Prueba rápida de recorte cover sin upscale para distintos formatos.

Ejecutar:
  python backend/jobs/crop_regression_test.py
"""
import os
import sys
import tempfile

import django
from PIL import Image


def _setup_django() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()


def _assert_square(image: Image.Image) -> None:
    if image.width != image.height:
        raise AssertionError(f"Resultado no cuadrado: {image.width}x{image.height}")


def _run_case(fmt: str, width: int, height: int) -> None:
    from jobs.services import _prepare_image

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, f"input.{fmt}")
        img = Image.new('RGB', (width, height), (20, 120, 200))
        img.save(path)

        with Image.open(path) as opened:
            prepared, meta = _prepare_image(
                opened,
                target_size=(1080, 1080),
                resize_mode='cover',
                no_upscale=True,
                crop_data=None,
                keep_alpha=False,
            )
            _assert_square(prepared)
            if prepared.width > width or prepared.height > height:
                raise AssertionError("Se aplicó upscale cuando no debía.")
            if meta.get('resize_mode') != 'cover':
                raise AssertionError("No se aplicó cover en el procesamiento.")


def main() -> None:
    _setup_django()

    # Caso grande: debe salir 1080x1080
    for fmt in ('jpg', 'png', 'webp'):
        _run_case(fmt, 2000, 1000)

    # Caso pequeño: no upscale, pero cuadrado (800x800)
    for fmt in ('jpg', 'png', 'webp'):
        _run_case(fmt, 800, 400)

    print("OK: recorte cover sin upscale mantiene aspecto 1:1.")


if __name__ == '__main__':
    main()
