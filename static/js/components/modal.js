// Modal accesible en Preact sin dependencias externas (soporta variantes amber/red para alertas)
import { useEffect, useRef } from '../../vendor/hooks.mjs';
import { html } from '../../vendor/htm-preact.mjs';

export function Modal({
    id,
    isOpen,
    onClose,
    title,
    variant = 'default',
    footer = null,
    children,
}) {
    const dialogRef = useRef(null);
    const prevFocusRef = useRef(null);
    const onCloseRef = useRef(onClose);
    onCloseRef.current = onClose;

    // Depender únicamente de [isOpen] evita robar el foco hacia el primer input en cada pulsación de tecla
    useEffect(() => {
        if (!isOpen) {
            if (prevFocusRef.current && typeof prevFocusRef.current.focus === 'function') {
                prevFocusRef.current.focus();
                prevFocusRef.current = null;
            }
            return undefined;
        }

        prevFocusRef.current = typeof document !== 'undefined' ? document.activeElement : null;
        const focusTimer = window.setTimeout(() => {
            const firstInput = dialogRef.current?.querySelector(
                'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]):not(.parq-modal-close)'
            );
            firstInput?.focus();
        }, 40);

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                onCloseRef.current?.();
            }
        };
        document.addEventListener('keydown', handleKeyDown);

        return () => {
            window.clearTimeout(focusTimer);
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [isOpen]);

    const dialogVariantClass =
        variant === 'warning-amber'
            ? 'modal-warning-amber'
            : variant === 'danger-red'
            ? 'modal-danger-red'
            : '';

    const headerVariantClass =
        variant === 'warning-amber'
            ? 'header-warning-amber'
            : variant === 'danger-red'
            ? 'header-danger-red'
            : '';

    const titleId = `${id}-title`;

    return html`
        <div
            class=${`parq-modal-backdrop ${isOpen ? 'is-open' : ''}`}
            id=${id}
            aria-hidden=${isOpen ? 'false' : 'true'}
            role="dialog"
            aria-modal="true"
            aria-labelledby=${titleId}
            onClick=${(e) => {
                if (e.target === e.currentTarget) {
                    onClose?.();
                }
            }}
        >
            <div class=${`parq-modal-dialog ${dialogVariantClass}`} ref=${dialogRef}>
                <div class=${`parq-modal-header ${headerVariantClass}`}>
                    <h5 class="parq-modal-title" id=${titleId}>${title}</h5>
                    <button
                        type="button"
                        class="parq-modal-close"
                        aria-label="Cerrar"
                        onClick=${() => onClose?.()}
                    >
                        ×
                    </button>
                </div>

                ${isOpen ? children : null}
                ${isOpen && footer ? html`<div class="parq-modal-footer">${footer}</div>` : null}
            </div>
        </div>
    `;
}
