import type { MouseEvent as ReactMouseEvent } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { useI18n } from '../services/i18n';
type CropRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type CropData = {
  crop_x: number;
  crop_y: number;
  crop_w: number;
  crop_h: number;
};

type DragMode = 'move' | 'nw' | 'ne' | 'sw' | 'se' | null;

interface CropModalProps {
  open: boolean;
  imageUrl: string;
  aspect: number;
  initialCrop?: CropData | null;
  onSave: (crop: CropData) => void;
  onCancel: () => void;
}

// Tamaño mínimo visible del recorte en pantalla (px).
const MIN_CROP_SIZE = 40;

export function CropModal({ open, imageUrl, aspect, initialCrop, onSave, onCancel }: CropModalProps) {
  const { t } = useI18n();
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [crop, setCrop] = useState<CropRect | null>(null);
  const [dragMode, setDragMode] = useState<DragMode>(null);
  const dragRef = useRef<{ startX: number; startY: number; startCrop: CropRect } | null>(null);

  // Asegura un ratio válido para evitar divisiones por cero.
  const safeAspect = useMemo(() => (aspect && Number.isFinite(aspect) && aspect > 0 ? aspect : 1), [aspect]);

  useEffect(() => {
    if (!open) return;
    setTimeout(() => {
      if (!imgRef.current) return;
      const { width, height } = imgRef.current.getBoundingClientRect();
      setImageSize({ width, height });
    }, 0);
  }, [open, imageUrl]);

  useEffect(() => {
    if (!imageSize.width || !imageSize.height) return;
    if (initialCrop) {
      setCrop({
        x: initialCrop.crop_x * imageSize.width,
        y: initialCrop.crop_y * imageSize.height,
        width: initialCrop.crop_w * imageSize.width,
        height: initialCrop.crop_h * imageSize.height,
      });
      return;
    }
    const { width, height } = getDefaultCrop(imageSize.width, imageSize.height, safeAspect);
    setCrop({
      x: (imageSize.width - width) / 2,
      y: (imageSize.height - height) / 2,
      width,
      height,
    });
  }, [imageSize, initialCrop, safeAspect]);

  useEffect(() => {
    if (!dragMode) return;
    const onMove = (event: MouseEvent) => {
      if (!dragRef.current || !crop) return;
      const dx = event.clientX - dragRef.current.startX;
      const dy = event.clientY - dragRef.current.startY;
      const { startCrop } = dragRef.current;
      const updated = updateCrop(
        dragMode,
        startCrop,
        dx,
        dy,
        imageSize.width,
        imageSize.height,
        safeAspect,
      );
      setCrop(updated);
    };
    const onUp = () => {
      setDragMode(null);
      dragRef.current = null;
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [dragMode, crop, imageSize, safeAspect]);

  if (!open) return null;

  const handleReset = () => {
    const { width, height } = getDefaultCrop(imageSize.width, imageSize.height, safeAspect);
    setCrop({
      x: (imageSize.width - width) / 2,
      y: (imageSize.height - height) / 2,
      width,
      height,
    });
  };

  const handleSave = () => {
    if (!crop || !imageSize.width || !imageSize.height) return;
    // Normaliza el recorte a coordenadas 0..1.
    onSave({
      crop_x: clamp(crop.x / imageSize.width, 0, 1),
      crop_y: clamp(crop.y / imageSize.height, 0, 1),
      crop_w: clamp(crop.width / imageSize.width, 0, 1),
      crop_h: clamp(crop.height / imageSize.height, 0, 1),
    });
  };

  const startDrag = (mode: DragMode) => (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!crop) return;
    event.preventDefault();
    event.stopPropagation();
    setDragMode(mode);
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      startCrop: crop,
    };
  };

  return (
    <div className="modal-backdrop" onMouseDown={onCancel}>
      <div className="modal" onMouseDown={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>{t.cropTitle}</h2>
            <p className="muted">{t.cropSubtitle}</p>
          </div>
        </header>

        <div className="crop-stage">
          <img
            ref={imgRef}
            src={imageUrl}
            alt={t.original}
            className="crop-image"
            onLoad={() => {
              if (!imgRef.current) return;
              const { width, height } = imgRef.current.getBoundingClientRect();
              setImageSize({ width, height });
            }}
          />
          {crop && (
            <div
              className="crop-box"
              style={{
                left: `${crop.x}px`,
                top: `${crop.y}px`,
                width: `${crop.width}px`,
                height: `${crop.height}px`,
              }}
              onMouseDown={startDrag('move')}
            >
              <span className="crop-handle handle-nw" onMouseDown={startDrag('nw')} />
              <span className="crop-handle handle-ne" onMouseDown={startDrag('ne')} />
              <span className="crop-handle handle-sw" onMouseDown={startDrag('sw')} />
              <span className="crop-handle handle-se" onMouseDown={startDrag('se')} />
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button className="ghost" type="button" onClick={handleReset}>
            {t.cropReset}
          </button>
          <button className="ghost" type="button" onClick={onCancel}>
            {t.cropCancel}
          </button>
          <button className="primary" type="button" onClick={handleSave}>
            {t.cropSave}
          </button>
        </div>
      </div>
    </div>
  );
}

function getDefaultCrop(
  containerWidth: number,
  containerHeight: number,
  aspect: number,
): { width: number; height: number } {
  // Crea un recorte inicial centrado que respeta el aspecto.
  if (!containerWidth || !containerHeight) {
    return { width: MIN_CROP_SIZE, height: MIN_CROP_SIZE };
  }
  const containerRatio = containerWidth / containerHeight;
  if (containerRatio > aspect) {
    const height = containerHeight;
    const width = height * aspect;
    return { width, height };
  }
  const width = containerWidth;
  const height = width / aspect;
  return { width, height };
}

function updateCrop(
  mode: DragMode,
  start: CropRect,
  dx: number,
  dy: number,
  maxW: number,
  maxH: number,
  aspect: number,
): CropRect {
  // Ajusta el rectángulo manteniendo el ratio al redimensionar o mover.
  if (mode === 'move') {
    return clampCrop(
      {
        x: start.x + dx,
        y: start.y + dy,
        width: start.width,
        height: start.height,
      },
      maxW,
      maxH,
    );
  }

  let width = start.width;
  let height = start.height;
  let x = start.x;
  let y = start.y;

  if (mode === 'se') {
    width = start.width + dx;
    height = width / aspect;
  }
  if (mode === 'ne') {
    width = start.width + dx;
    height = width / aspect;
    y = start.y + (start.height - height);
  }
  if (mode === 'sw') {
    width = start.width - dx;
    height = width / aspect;
    x = start.x + (start.width - width);
  }
  if (mode === 'nw') {
    width = start.width - dx;
    height = width / aspect;
    x = start.x + (start.width - width);
    y = start.y + (start.height - height);
  }

  width = Math.max(width, MIN_CROP_SIZE);
  height = width / aspect;

  if (height > maxH) {
    height = maxH;
    width = height * aspect;
  }
  if (width > maxW) {
    width = maxW;
    height = width / aspect;
  }

  return clampCrop({ x, y, width, height }, maxW, maxH);
}

function clampCrop(crop: CropRect, maxW: number, maxH: number): CropRect {
  const width = Math.min(crop.width, maxW);
  const height = Math.min(crop.height, maxH);
  const x = clamp(crop.x, 0, Math.max(0, maxW - width));
  const y = clamp(crop.y, 0, Math.max(0, maxH - height));
  return { x, y, width, height };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
