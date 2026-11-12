// Contenedor reactivo de notificaciones tipo toast conectado al store global
import { html } from '../../vendor/htm-preact.mjs';
import { dismissToast, toasts } from '../store/app_store.js';

const TOAST_TITLES = {
    success: 'Operación exitosa',
    warning: 'Atención',
    error: 'Error en la operación',
    info: 'Información',
};

export function ToastContainer() {
    const items = toasts.value;
    if (!items.length) return null;

    return html`
        <div class="parq-toast-container" role="region" aria-label="Notificaciones del sistema">
            ${items.map((item) => {
                const type = item.type || 'info';
                return html`
                    <div
                        key=${item.id}
                        class=${`parq-toast toast-${type}`}
                        role=${type === 'error' ? 'alert' : 'status'}
                    >
                        <div>
                            <div class="parq-toast-title">${TOAST_TITLES[type] || TOAST_TITLES.info}</div>
                            <div class="parq-toast-msg">${item.message}</div>
                        </div>
                        <button
                            type="button"
                            class="parq-modal-close"
                            aria-label="Cerrar notificación"
                            onClick=${() => dismissToast(item.id)}
                        >
                            ×
                        </button>
                    </div>
                `;
            })}
        </div>
    `;
}
