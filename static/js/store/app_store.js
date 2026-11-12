// Estado global reactivo de la SPA usando Signals sin paso de compilación
import { batch, computed, signal } from '../../vendor/signals.mjs';
import { apiRequest, setUnauthorizedHandler } from '../api.js';
import { applyTheme, getStoredTheme } from '../ui/theme.js';

export const ROUTE_PATHS = {
    operacion: 'index.html',
    registros: 'registros.html',
    configuracion: 'configuracion.html',
    login: 'login.html',
};

const ROUTE_TITLES = {
    operacion: 'Operación — Parqueadero POS',
    registros: 'Registros e Historial — Parqueadero POS',
    configuracion: 'Configuración — Parqueadero POS',
    login: 'Acceso — Parqueadero POS',
};

export function pathToRoute(pathname) {
    const clean = String(pathname || '').toLowerCase();
    if (clean.endsWith('login.html') || clean.endsWith('/login')) return 'login';
    if (clean.endsWith('registros.html') || clean.endsWith('/registros')) return 'registros';
    if (clean.endsWith('configuracion.html') || clean.endsWith('/configuracion')) return 'configuracion';
    return 'operacion';
}

export function routeToPath(route) {
    return ROUTE_PATHS[route] || ROUTE_PATHS.operacion;
}

const initialRoute =
    typeof window !== 'undefined' ? pathToRoute(window.location.pathname) : 'operacion';

export const currentUser = signal(null);
export const isAdmin = computed(() => (currentUser.value?.rol || '').toLowerCase() === 'admin');
export const authChecked = signal(false);
export const currentRoute = signal(initialRoute);
export const intendedRoute = signal(initialRoute !== 'login' ? initialRoute : 'operacion');

export const theme = signal(typeof document !== 'undefined' ? getStoredTheme() : 'light');
export const isOnline = signal(typeof navigator !== 'undefined' ? navigator.onLine !== false : true);
export const toasts = signal([]);

export const tiposVehiculo = signal([]);
export const tiposLoading = signal(false);
export const tiposLoaded = signal(false);
export const activeTicketPreview = signal(null);

let nextToastId = 1;
const sessionResetHooks = new Set();

// Desacopla stores hijos sin crear importaciones circulares con app_store
export function registerSessionResetHook(fn) {
    if (typeof fn === 'function') {
        sessionResetHooks.add(fn);
    }
    return () => sessionResetHooks.delete(fn);
}

function runSessionResetHooks() {
    sessionResetHooks.forEach((fn) => {
        try {
            fn();
        } catch (_) {}
    });
}

export function dismissToast(id) {
    toasts.value = toasts.value.filter((item) => item.id !== id);
}

export function showToast(message, type = 'info', durationMs = 4200) {
    const id = nextToastId;
    nextToastId += 1;

    const entry = { id, message: String(message || ''), type };
    toasts.value = [...toasts.value.slice(-4), entry];

    if (durationMs > 0 && typeof window !== 'undefined') {
        window.setTimeout(() => dismissToast(id), durationMs);
    }
    return id;
}

export function initThemeState() {
    const applied = applyTheme(typeof document !== 'undefined' ? getStoredTheme() : theme.value);
    theme.value = applied;
    return applied;
}

export function toggleAppTheme() {
    const next = applyTheme(theme.value === 'dark' ? 'light' : 'dark');
    theme.value = next;
    return next;
}

function applyDocumentMeta(route) {
    if (typeof document !== 'undefined') {
        document.title = ROUTE_TITLES[route] || ROUTE_TITLES.operacion;
        document.body?.classList.toggle('login-body', route === 'login');
    }
}

export function navigate(route, { replace = false, syncHistory = true } = {}) {
    let target = ROUTE_PATHS[route] ? route : 'operacion';

    if (!currentUser.value && target !== 'login') {
        intendedRoute.value = target;
        target = 'login';
    } else if (currentUser.value && target === 'login') {
        target = 'operacion';
    }

    currentRoute.value = target;
    applyDocumentMeta(target);

    if (syncHistory && typeof window !== 'undefined' && window.history) {
        const desiredPath = routeToPath(target);
        const currentFile = pathToRoute(window.location.pathname);
        if (currentFile !== target || replace) {
            const method = replace ? 'replaceState' : 'pushState';
            window.history[method]({ route: target }, '', desiredPath);
        }
    }
}

export function handleUnauthorized() {
    batch(() => {
        if (currentRoute.value !== 'login') {
            intendedRoute.value = currentRoute.value;
        }
        currentUser.value = null;
        tiposVehiculo.value = [];
        tiposLoaded.value = false;
        activeTicketPreview.value = null;
        runSessionResetHooks();
    });
    navigate('login', { replace: true });
}

export async function initAuthSession() {
    setUnauthorizedHandler(() => handleUnauthorized());

    try {
        const user = await apiRequest('/api/auth/me', {
            method: 'GET',
            redirectOn401: false,
        });
        batch(() => {
            currentUser.value = user;
            authChecked.value = true;
        });
        const dest = currentRoute.value === 'login' ? 'operacion' : currentRoute.value;
        navigate(dest, { replace: true });
        return user;
    } catch (_) {
        batch(() => {
            currentUser.value = null;
            authChecked.value = true;
        });
        navigate('login', { replace: true });
        return null;
    }
}

export async function performLogin(nombre, password) {
    await apiRequest('/api/auth/login', {
        method: 'POST',
        body: { nombre, password },
        redirectOn401: false,
    });

    const user = await apiRequest('/api/auth/me', {
        method: 'GET',
        redirectOn401: false,
    });

    const nextTarget =
        intendedRoute.value && intendedRoute.value !== 'login' ? intendedRoute.value : 'operacion';

    batch(() => {
        currentUser.value = user;
        authChecked.value = true;
        intendedRoute.value = 'operacion';
    });

    navigate(nextTarget, { replace: true });
    return user;
}

export async function performLogout() {
    try {
        await apiRequest('/api/auth/logout', { method: 'POST', redirectOn401: false });
    } catch (_) {
        // Incluso si expiró el token o falló red, limpiar estado local de sesión
    }

    batch(() => {
        currentUser.value = null;
        intendedRoute.value = 'operacion';
        tiposVehiculo.value = [];
        tiposLoaded.value = false;
        activeTicketPreview.value = null;
        runSessionResetHooks();
    });
    navigate('login', { replace: true });
    showToast('Sesión cerrada.', 'info', 2500);
}

export async function ensureTiposLoaded(force = false) {
    if (tiposLoading.value) return tiposVehiculo.value;
    if (tiposLoaded.value && !force) return tiposVehiculo.value;

    tiposLoading.value = true;
    try {
        const data = await apiRequest('/tipos-vehiculo');
        batch(() => {
            tiposVehiculo.value = Array.isArray(data) ? data : [];
            tiposLoaded.value = true;
        });
        return tiposVehiculo.value;
    } finally {
        tiposLoading.value = false;
    }
}

export function upsertTipoInStore(savedTipo) {
    if (!savedTipo || !savedTipo.id) return;
    const list = tiposVehiculo.value;
    const idx = list.findIndex((item) => item.id === savedTipo.id);
    if (idx >= 0) {
        tiposVehiculo.value = list.map((item) => (item.id === savedTipo.id ? savedTipo : item));
    } else {
        tiposVehiculo.value = [...list, savedTipo];
    }
    tiposLoaded.value = true;
}

// Abre la vista previa del ticket superpuesta en la misma pestaña sin abrir ventanas emergentes
export async function openTicketPreview(ticketOrId, tipo = 'ingreso', { autoPrint = true } = {}) {
    if (!ticketOrId) return null;

    if (typeof ticketOrId === 'object' && ticketOrId.placa) {
        activeTicketPreview.value = {
            ticket: ticketOrId,
            tipo,
            autoPrint,
            openedAt: Date.now(),
        };
        return ticketOrId;
    }

    const id = typeof ticketOrId === 'object' ? ticketOrId.id : ticketOrId;
    try {
        const ticket = await apiRequest(`/ticket/${encodeURIComponent(id)}`);
        activeTicketPreview.value = {
            ticket,
            tipo,
            autoPrint,
            openedAt: Date.now(),
        };
        return ticket;
    } catch (err) {
        showToast(err?.message || 'No se pudo cargar la vista previa del ticket.', 'error');
        return null;
    }
}

export function closeTicketPreview() {
    activeTicketPreview.value = null;
}

export function bindGlobalWindowEvents() {
    if (typeof window === 'undefined') return () => {};

    const onPopState = () => {
        const nextRoute = pathToRoute(window.location.pathname);
        navigate(nextRoute, { syncHistory: false });
    };
    const onOnline = () => {
        isOnline.value = true;
        showToast('Conexión restablecida con el servidor local.', 'success', 3000);
    };
    const onOffline = () => {
        isOnline.value = false;
        showToast('Se perdió la conexión con el servidor.', 'warning');
    };

    window.addEventListener('popstate', onPopState);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);

    return () => {
        window.removeEventListener('popstate', onPopState);
        window.removeEventListener('online', onOnline);
        window.removeEventListener('offline', onOffline);
    };
}
