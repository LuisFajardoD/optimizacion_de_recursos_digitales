import { useEffect, useRef } from 'react';

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  errorText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  message,
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  danger = false,
  errorText,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCancel();
        return;
      }

      if (event.key === 'Tab') {
        const cancelEl = cancelRef.current;
        const confirmEl = confirmRef.current;
        if (!cancelEl || !confirmEl) return;
        const isShift = event.shiftKey;
        const active = document.activeElement;

        if (!isShift && active === confirmEl) {
          event.preventDefault();
          cancelEl.focus();
        } else if (isShift && active === cancelEl) {
          event.preventDefault();
          confirmEl.focus();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="modal-overlay"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">{title}</h2>
        <p>{message}</p>
        {errorText && <p className="modal-error">{errorText}</p>}
        <div className="modal-actions">
          <button ref={cancelRef} type="button" className="ghost" onClick={onCancel}>
            {cancelText}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`ghost ${danger ? 'danger' : ''}`}
            onClick={onConfirm}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
