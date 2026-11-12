// Barra de navegación SPA reactiva con cambio de vista sin recarga de página
import { html } from '../../vendor/htm-preact.mjs';
import {
    currentRoute,
    currentUser,
    isAdmin,
    navigate,
    performLogout,
    theme,
    toggleAppTheme,
} from '../store/app_store.js';

export function Navbar() {
    const user = currentUser.value;
    const route = currentRoute.value;
    const admin = isAdmin.value;
    const currentTheme = theme.value;

    const userName = user?.nombre || 'Operador';
    const roleClass = admin ? 'role-admin' : 'role-cajero';
    const roleLabel = admin ? 'ADMIN' : 'CAJERO';
    const themeLabel = currentTheme === 'dark' ? '☀️ Claro' : '🌙 Oscuro';

    const handleNav = (e, targetRoute) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
            return;
        }
        e.preventDefault();
        navigate(targetRoute);
    };

    return html`
        <header class="parq-navbar" role="banner">
            <a
                class="parq-brand"
                href="index.html"
                onClick=${(e) => handleNav(e, 'operacion')}
            >
                <span class="parq-brand-mark" aria-hidden="true">P</span>
                <span>
                    Parqueadero Bahondo
                    <span class="parq-brand-subtitle">Control Operativo Vehicular</span>
                </span>
            </a>

            <nav class="parq-nav-links" aria-label="Navegación principal">
                <a
                    class=${`parq-nav-link ${route === 'operacion' ? 'active' : ''}`}
                    href="index.html"
                    onClick=${(e) => handleNav(e, 'operacion')}
                >
                    Operación
                </a>
                <a
                    class=${`parq-nav-link ${route === 'registros' ? 'active' : ''}`}
                    href="registros.html"
                    onClick=${(e) => handleNav(e, 'registros')}
                >
                    Registros
                </a>
                <a
                    class=${`parq-nav-link ${route === 'configuracion' ? 'active' : ''}`}
                    href="configuracion.html"
                    onClick=${(e) => handleNav(e, 'configuracion')}
                >
                    Configuración
                </a>
            </nav>

            <div class="parq-nav-actions">
                <div class="parq-user-pill" title="Usuario autenticado y rol activo">
                    <span class="parq-user-name" id="nav-user-name">${userName}</span>
                    <span class=${`parq-role-badge ${roleClass}`} id="nav-user-role">${roleLabel}</span>
                </div>
                <button
                    type="button"
                    class="parq-icon-btn"
                    id="btn-theme-toggle"
                    title="Cambiar modo de contraste"
                    onClick=${toggleAppTheme}
                >
                    ${themeLabel}
                </button>
                <button
                    type="button"
                    class="parq-icon-btn btn-logout"
                    id="btn-logout"
                    title="Cerrar sesión"
                    onClick=${performLogout}
                >
                    Salir
                </button>
            </div>
        </header>
    `;
}
