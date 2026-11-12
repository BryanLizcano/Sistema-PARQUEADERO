// Store reactivo para historial paginado, caché de vista y mutaciones locales sin recarga completa
import { batch, computed, signal } from '../../vendor/signals.mjs';
import { apiRequest } from '../api.js';
import { diffDaysInclusive, parseLocalDate } from '../components/period_picker.js';
import { isOnline, registerSessionResetHook, showToast } from './app_store.js';

export const PAGE_LIMIT = 50;

// Límites máximos de exportación (idénticos al backend services/export_service.py)
export const EXPORT_LIMITS = {
    dias: { maxDays: 20, label: 'Días: máximo 20 días por exportación' },
    semanas: { maxDays: 70, label: 'Semanas: máximo 10 semanas (70 días)' },
    mes: { maxDays: 31, label: 'Mes: máximo 1 mes (31 días)' },
    anio: { maxDays: 366, label: 'Año: solo años con registros en BD' },
};

export function validateExportRange(tipo, desdeStr, hastaStr) {
    const rule = EXPORT_LIMITS[tipo] || EXPORT_LIMITS.dias;
    if (!desdeStr || !hastaStr) {
        return {
            valid: false,
            days: 0,
            maxDays: rule.maxDays,
            message:
                tipo === 'anio'
                    ? 'No existen registros en la base de datos para exportar por año.'
                    : 'Seleccione el periodo que desea exportar.',
            ruleLabel: rule.label,
        };
    }

    const desde = parseLocalDate(desdeStr);
    const hasta = parseLocalDate(hastaStr);
    if (!desde || !hasta) {
        return {
            valid: false,
            days: 0,
            maxDays: rule.maxDays,
            message: 'Formato de fecha inválido.',
            ruleLabel: rule.label,
        };
    }

    if (desde > hasta) {
        return {
            valid: false,
            days: 0,
            maxDays: rule.maxDays,
            message: 'La fecha "Desde" no puede ser mayor que la fecha "Hasta".',
            ruleLabel: rule.label,
        };
    }

    const days = diffDaysInclusive(desdeStr, hastaStr);
    if (days > rule.maxDays) {
        return {
            valid: false,
            days,
            maxDays: rule.maxDays,
            message: `Rango excedido: seleccionó ${days} días y el límite para "${tipo}" es ${rule.maxDays} días.`,
            ruleLabel: rule.label,
        };
    }

    return {
        valid: true,
        days,
        maxDays: rule.maxDays,
        message: `✓ Rango válido (${days} de ${rule.maxDays} días máx. permitidos).`,
        ruleLabel: rule.label,
    };
}

export function debounce(fn, delayMs = 220) {
    let timerId = null;
    const setT = typeof window !== 'undefined' ? window.setTimeout.bind(window) : setTimeout;
    const clearT = typeof window !== 'undefined' ? window.clearTimeout.bind(window) : clearTimeout;

    return function (...args) {
        if (timerId) clearT(timerId);
        timerId = setT(() => {
            timerId = null;
            fn.apply(this, args);
        }, delayMs);
    };
}

export const registros = signal([]);
export const registrosPage = signal(1);
export const registrosTotal = signal(0);
export const registrosTotalPages = signal(1);
export const filtroPlaca = signal('');
export const filtroEstado = signal('');

export const registrosLoading = signal(false);
export const registrosLoaded = signal(false);
export const registrosError = signal(null);
export const registrosPerfMs = signal(null);
export const registrosStale = signal(false);

export const availableYears = signal([]);
export const exportYearsLoaded = signal(false);

export const kpiStats = computed(() => {
    const rows = registros.value;
    let activos = 0;
    let finalizados = 0;
    let recaudo = 0;

    for (let i = 0; i < rows.length; i += 1) {
        const t = rows[i];
        if (t.fecha_salida || t.estado === 'FINALIZADO') {
            finalizados += 1;
        } else {
            activos += 1;
        }
        const monto = Number(t.precio_final ?? t.precio_total ?? 0);
        if (!Number.isNaN(monto) && monto > 0) {
            recaudo += monto;
        }
    }

    return { activos, finalizados, recaudo };
});

let activeAbortController = null;
let skeletonDelayTimer = null;

export function resetRegistrosStore() {
    if (activeAbortController) {
        activeAbortController.abort();
        activeAbortController = null;
    }
    if (skeletonDelayTimer && typeof window !== 'undefined') {
        window.clearTimeout(skeletonDelayTimer);
        skeletonDelayTimer = null;
    }

    batch(() => {
        registros.value = [];
        registrosPage.value = 1;
        registrosTotal.value = 0;
        registrosTotalPages.value = 1;
        filtroPlaca.value = '';
        filtroEstado.value = '';
        registrosLoading.value = false;
        registrosLoaded.value = false;
        registrosError.value = null;
        registrosPerfMs.value = null;
        registrosStale.value = false;
        availableYears.value = [];
        exportYearsLoaded.value = false;
    });
}

registerSessionResetHook(resetRegistrosStore);

export async function loadRegistros(
    page = registrosPage.value,
    { background = false, showSkeleton = false } = {}
) {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        isOnline.value = false;
        registrosError.value = { status: 0, message: 'Sin conexión de red local.' };
        registrosLoading.value = false;
        return;
    }

    if (activeAbortController) {
        activeAbortController.abort();
    }
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    activeAbortController = controller;

    if (skeletonDelayTimer && typeof window !== 'undefined') {
        window.clearTimeout(skeletonDelayTimer);
        skeletonDelayTimer = null;
    }

    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
    registrosError.value = null;

    // Mostrar skeletons inmediato solo en carga inicial o pedido explícito; en cambios de página/filtro
    // diferir 140ms evita parpadeo en respuestas locales rápidas (< 50ms)
    if (!registrosLoaded.value || showSkeleton) {
        registrosLoading.value = true;
    } else if (!background && typeof window !== 'undefined') {
        skeletonDelayTimer = window.setTimeout(() => {
            registrosLoading.value = true;
        }, 140);
    }

    const params = new URLSearchParams({
        page: String(page),
        limit: String(PAGE_LIMIT),
    });
    const placa = filtroPlaca.value.trim();
    const estado = filtroEstado.value;
    if (placa) params.set('placa', placa);
    if (estado) params.set('estado', estado);

    try {
        const res = await apiRequest(`/api/registros?${params.toString()}`, {
            signal: controller?.signal,
        });

        if (skeletonDelayTimer && typeof window !== 'undefined') {
            window.clearTimeout(skeletonDelayTimer);
            skeletonDelayTimer = null;
        }

        const total = Number(res.total || 0);
        const totalPages = Math.max(1, Number(res.totalPages || 1));
        const currentPage = Number(res.page || page);
        const rows = Array.isArray(res.data) ? res.data : [];

        const elapsed = Math.round(
            (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0
        );

        batch(() => {
            registros.value = rows;
            registrosPage.value = currentPage;
            registrosTotal.value = total;
            registrosTotalPages.value = totalPages;
            registrosLoading.value = false;
            registrosLoaded.value = true;
            registrosStale.value = false;
            registrosError.value = null;
            registrosPerfMs.value = elapsed;
        });

        isOnline.value = true;
    } catch (err) {
        if (err && err.name === 'AbortError') {
            return;
        }
        if (skeletonDelayTimer && typeof window !== 'undefined') {
            window.clearTimeout(skeletonDelayTimer);
            skeletonDelayTimer = null;
        }

        const offline = err?.status === 0;
        if (offline) {
            isOnline.value = false;
        }
        batch(() => {
            registrosLoading.value = false;
            registrosError.value = {
                status: err?.status ?? 500,
                message: err?.message || 'Error inesperado al consultar registros.',
            };
        });
        if (!background) {
            showToast(err?.message || 'Error al cargar registros.', 'error');
        }
    } finally {
        if (activeAbortController === controller) {
            activeAbortController = null;
        }
    }
}

export function prependTicketInStore(ticket) {
    if (!ticket || !ticket.id || !registrosLoaded.value) return;

    const matchesFilter =
        (!filtroPlaca.value || ticket.placa?.includes(filtroPlaca.value)) &&
        (!filtroEstado.value || ticket.estado === filtroEstado.value);

    if (!matchesFilter || registrosPage.value !== 1) {
        registrosStale.value = true;
        return;
    }

    batch(() => {
        const nextTotal = registrosTotal.value + 1;
        registros.value = [ticket, ...registros.value.filter((r) => r.id !== ticket.id)].slice(
            0,
            PAGE_LIMIT
        );
        registrosTotal.value = nextTotal;
        registrosTotalPages.value = Math.max(1, Math.ceil(nextTotal / PAGE_LIMIT));
        exportYearsLoaded.value = false;
    });
}

// Muta únicamente el ticket afectado en memoria para evitar re-cargas completas y parpadeos
export function updateTicketInStore(updatedTicket) {
    if (!updatedTicket || !updatedTicket.id) return;
    const rows = registros.value;
    const exists = rows.some((item) => item.id === updatedTicket.id);
    if (!exists) {
        registrosStale.value = true;
        return;
    }

    const updatedEstado = updatedTicket.estado || (updatedTicket.fecha_salida ? 'FINALIZADO' : 'ACTIVO');
    const stillMatchesEstado = !filtroEstado.value || filtroEstado.value === updatedEstado;

    if (!stillMatchesEstado) {
        removeTicketFromStore(updatedTicket.id);
        return;
    }

    registros.value = rows.map((item) =>
        item.id === updatedTicket.id ? { ...item, ...updatedTicket } : item
    );
}

export function removeTicketFromStore(ticketId) {
    const prevRows = registros.value;
    const nextRows = prevRows.filter((item) => item.id !== ticketId);
    if (nextRows.length === prevRows.length) return;

    batch(() => {
        registros.value = nextRows;
        const nextTotal = Math.max(0, registrosTotal.value - 1);
        registrosTotal.value = nextTotal;
        registrosTotalPages.value = Math.max(1, Math.ceil(nextTotal / PAGE_LIMIT));
    });

    if (nextRows.length === 0 && registrosPage.value > 1) {
        loadRegistros(registrosPage.value - 1, { showSkeleton: false });
    }
}

export async function loadExportYears(force = false) {
    if (exportYearsLoaded.value && !force) return availableYears.value;
    try {
        const res = await apiRequest('/api/exportar/anios');
        const list = Array.isArray(res?.anios) ? res.anios.map(Number).filter(Boolean) : [];
        batch(() => {
            availableYears.value = list;
            exportYearsLoaded.value = true;
        });
        return list;
    } catch (_) {
        availableYears.value = [];
        return [];
    }
}
