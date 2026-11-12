// Vista SPA de inicio de sesión unificado para Administrador y Cajero
import { useEffect, useRef, useState } from '../../vendor/hooks.mjs';
import { html } from '../../vendor/htm-preact.mjs';
import { performLogin, showToast, theme, toggleAppTheme } from '../store/app_store.js';

export function LoginView() {
    const [nombre, setNombre] = useState('');
    const [password, setPassword] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const inputUserRef = useRef(null);

    useEffect(() => {
        inputUserRef.current?.focus();
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        const userTrim = nombre.trim();
        if (!userTrim || !password) {
            showToast('Ingrese su usuario y contraseña.', 'warning');
            return;
        }

        setSubmitting(true);
        try {
            await performLogin(userTrim, password);
        } catch (err) {
            showToast(err?.message || 'Credenciales inválidas.', 'error');
            setSubmitting(false);
            setPassword('');
        }
    };

    const currentTheme = theme.value;

    return html`
        <main class="login-shell spa-view-enter">
            <div class="login-card">
                <div class="login-card-header">
                    <div class="login-logo-badge" aria-hidden="true">P</div>
                    <h1 class="h4 fw-bold mb-1">Parqueadero Bahondo</h1>
                    <p class="mb-0 small" style="color: var(--slate-200);">
                        Sistema de Control Operativo y Liquidación Vehicular
                    </p>
                </div>

                <div class="login-card-body">
                    <div class="login-role-hint">
                        <span>Acceso unificado para <strong>Administrador</strong> y <strong>Cajero</strong></span>
                    </div>

                    <form id="form-login" autocomplete="on" onSubmit=${handleSubmit}>
                        <div class="mb-3">
                            <label class="parq-label" for="login-nombre">Usuario</label>
                            <input
                                ref=${inputUserRef}
                                type="text"
                                id="login-nombre"
                                class="parq-input"
                                placeholder="Ej. Admin o Cajero"
                                autocomplete="username"
                                value=${nombre}
                                onInput=${(e) => setNombre(e.target.value)}
                                required
                            />
                        </div>

                        <div class="mb-4">
                            <label class="parq-label" for="login-password">Contraseña</label>
                            <input
                                type="password"
                                id="login-password"
                                class="parq-input"
                                placeholder="••••••••"
                                autocomplete="current-password"
                                value=${password}
                                onInput=${(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>

                        <button
                            type="submit"
                            id="btn-login-submit"
                            class="btn-parq btn-parq-sage btn-parq-lg w-100 mb-3"
                            disabled=${submitting}
                        >
                            ${submitting ? 'Verificando credenciales...' : 'Ingresar al Sistema'}
                        </button>

                        <div class="text-center">
                            <button
                                type="button"
                                id="btn-login-theme"
                                class="btn-parq btn-parq-outline btn-parq-sm"
                                onClick=${toggleAppTheme}
                            >
                                ${currentTheme === 'dark' ? '☀️ Modo Claro' : '🌙 Modo Oscuro Suave'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </main>
    `;
}
