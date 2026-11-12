// Punto de entrada único de la SPA Preact + Signals (cero build step y cero CDN)
import { useEffect } from '../vendor/hooks.mjs';
import { html } from '../vendor/htm-preact.mjs';
import { render } from '../vendor/preact.mjs';
import { Navbar } from './components/navbar.js';
import { TicketPreviewModal } from './components/ticket_modal.js';
import { ToastContainer } from './components/toast_container.js';
import {
    authChecked,
    bindGlobalWindowEvents,
    currentRoute,
    currentUser,
    initAuthSession,
    initThemeState,
} from './store/app_store.js';
import { ConfiguracionView } from './views/configuracion_view.js';
import { LoginView } from './views/login_view.js';
import { OperacionView } from './views/operacion_view.js';
import { RegistrosView } from './views/registros_view.js';

function App() {
    useEffect(() => {
        initThemeState();
        const unbindEvents = bindGlobalWindowEvents();
        initAuthSession();
        return unbindEvents;
    }, []);

    const checked = authChecked.value;
    const user = currentUser.value;
    const route = currentRoute.value;

    if (!checked) {
        return html`
            <div class="spa-boot-screen">
                <div class="parq-brand-mark" aria-hidden="true">P</div>
                <span class="small" style="color: var(--text-muted); font-weight: 600;">
                    Iniciando Parqueadero POS...
                </span>
            </div>
        `;
    }

    if (!user || route === 'login') {
        return html`
            <${ToastContainer} />
            <${LoginView} />
        `;
    }

    let activeView = null;
    if (route === 'registros') {
        activeView = html`<${RegistrosView} />`;
    } else if (route === 'configuracion') {
        activeView = html`<${ConfiguracionView} />`;
    } else {
        activeView = html`<${OperacionView} />`;
    }

    return html`
        <${ToastContainer} />
        <${TicketPreviewModal} />
        <div class="app-container page-shell">
            <${Navbar} />
            <main key=${route}>
                ${activeView}
            </main>
        </div>
    `;
}

const rootEl = typeof document !== 'undefined' ? document.getElementById('app') : null;
if (rootEl) {
    render(html`<${App} />`, rootEl);
}
