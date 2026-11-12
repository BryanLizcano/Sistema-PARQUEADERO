// Cliente HTTP centralizado con soporte de sesión por cookie HttpOnly y formato de error uniforme {error: {codigo, mensaje}}

let unauthorizedHandler = null;

// Permite a la SPA cambiar de vista al login por señal reactiva sin recargar la página
export function setUnauthorizedHandler(handler) {
    unauthorizedHandler = typeof handler === 'function' ? handler : null;
}

export class ApiError extends Error {
    constructor(codigo, mensaje, status) {
        super(mensaje);
        this.name = 'ApiError';
        this.codigo = codigo || 'ERROR_DESCONOCIDO';
        this.status = status;
    }
}

export async function apiRequest(url, options = {}) {
    const {
        method = 'GET',
        body = undefined,
        headers = {},
        redirectOn401 = true,
        signal = undefined,
    } = options;

    const reqHeaders = { ...headers };
    let reqBody = body;

    if (body !== undefined && !(body instanceof FormData)) {
        reqHeaders['Content-Type'] = 'application/json';
        reqBody = JSON.stringify(body);
    }

    let response;
    try {
        response = await fetch(url, {
            method,
            headers: reqHeaders,
            body: reqBody,
            credentials: 'same-origin',
            signal,
        });
    } catch (networkErr) {
        if (networkErr && networkErr.name === 'AbortError') {
            throw networkErr;
        }
        throw new ApiError(
            'SIN_CONEXION',
            'No hay conexión con el servidor local del parqueadero. Verifique la red o el servicio.',
            0
        );
    }

    if (response.status === 401 && redirectOn401) {
        if (unauthorizedHandler) {
            unauthorizedHandler();
        } else if (typeof window !== 'undefined' && !window.location.pathname.endsWith('login.html')) {
            window.location.href = 'login.html';
        }
    }

    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const payload = isJson ? await response.json().catch(() => null) : null;

    if (!response.ok) {
        const codigo = payload?.error?.codigo || `HTTP_${response.status}`;
        const mensaje =
            payload?.error?.mensaje ||
            payload?.detail ||
            `Error en la solicitud (${response.status})`;
        throw new ApiError(codigo, mensaje, response.status);
    }

    return payload;
}
