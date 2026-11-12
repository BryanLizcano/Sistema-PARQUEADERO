// Vista SPA de configuración: tarifas solo para Admin (con modal de advertencia) y cambio de contraseña para todos
import { useEffect, useState } from '../../vendor/hooks.mjs';
import { html } from '../../vendor/htm-preact.mjs';
import { apiRequest } from '../api.js';
import { Modal } from '../components/modal.js';
import {
    ensureTiposLoaded,
    isAdmin,
    showToast,
    tiposLoading,
    tiposVehiculo,
    upsertTipoInStore,
} from '../store/app_store.js';
import { formatMoney } from '../ui/format.js';

export function ConfiguracionView() {
    const admin = isAdmin.value;
    const tipos = tiposVehiculo.value;
    const loadingTipos = tiposLoading.value;

    // Estado formulario de tarifa (Solo Admin)
    const [idEditando, setIdEditando] = useState(null);
    const [nombreTarifa, setNombreTarifa] = useState('');
    const [tHora, setTHora] = useState('');
    const [tDia, setTDia] = useState('');
    const [tNoche, setTNoche] = useState('');
    const [guardandoTarifa, setGuardandoTarifa] = useState(false);
    const [pendingPayload, setPendingPayload] = useState(null);

    // Estado cambio de contraseña (Admin y Cajero)
    const [pwdActual, setPwdActual] = useState('');
    const [pwdNueva, setPwdNueva] = useState('');
    const [pwdConfirmar, setPwdConfirmar] = useState('');
    const [cambiandoPwd, setCambiandoPwd] = useState(false);

    useEffect(() => {
        if (admin) {
            ensureTiposLoaded().catch((err) => {
                showToast(err?.message || 'Error al cargar tarifas configuradas.', 'error');
            });
        }
    }, [admin]);

    const cancelarEdicion = () => {
        setIdEditando(null);
        setPendingPayload(null);
        setNombreTarifa('');
        setTHora('');
        setTDia('');
        setTNoche('');
    };

    const iniciarEdicion = (tipo) => {
        setIdEditando(tipo.id);
        setNombreTarifa(tipo.nombre);
        setTHora(String(tipo.tarifa_hora));
        setTDia(String(tipo.tarifa_dia));
        setTNoche(String(tipo.tarifa_noche));
        showToast(`Editando tarifa "${tipo.nombre}".`, 'info', 2400);
    };

    const handleSubmitTipo = async (e) => {
        e.preventDefault();
        if (!admin) return;

        const payload = {
            nombre: nombreTarifa.trim().toUpperCase(),
            tarifa_hora: parseFloat(tHora),
            tarifa_dia: parseFloat(tDia),
            tarifa_noche: parseFloat(tNoche),
        };

        if (idEditando) {
            setPendingPayload(payload);
            return;
        }

        setGuardandoTarifa(true);
        try {
            const created = await apiRequest('/tipos-vehiculo', {
                method: 'POST',
                body: payload,
            });
            upsertTipoInStore(created);
            showToast(`Tipo de vehículo ${payload.nombre} creado con éxito.`, 'success');
            cancelarEdicion();
        } catch (err) {
            showToast(err?.message || 'No se pudo crear el tipo de vehículo.', 'error');
        } finally {
            setGuardandoTarifa(false);
        }
    };

    const confirmarActualizacionTarifa = async () => {
        if (!idEditando || !pendingPayload) return;
        setGuardandoTarifa(true);
        try {
            const updated = await apiRequest(`/tipos-vehiculo/${encodeURIComponent(idEditando)}`, {
                method: 'PUT',
                body: pendingPayload,
            });
            upsertTipoInStore(updated);
            showToast(`Tarifa ${pendingPayload.nombre} actualizada y registrada en auditoría.`, 'success');
            cancelarEdicion();
        } catch (err) {
            showToast(err?.message || 'No se pudo actualizar la tarifa.', 'error');
        } finally {
            setGuardandoTarifa(false);
        }
    };

    const handleCambiarPassword = async (e) => {
        e.preventDefault();
        if (!pwdActual) {
            showToast('Debe ingresar su contraseña actual.', 'warning');
            return;
        }
        if (pwdNueva.length < 4) {
            showToast('La nueva contraseña debe tener al menos 4 caracteres.', 'warning');
            return;
        }
        if (pwdNueva !== pwdConfirmar) {
            showToast('La confirmación de la nueva contraseña no coincide.', 'warning');
            return;
        }

        setCambiandoPwd(true);
        try {
            await apiRequest('/api/auth/cambiar-password', {
                method: 'POST',
                body: { password_actual: pwdActual, password_nueva: pwdNueva },
            });
            setPwdActual('');
            setPwdNueva('');
            setPwdConfirmar('');
            showToast(
                'Contraseña actualizada correctamente. Las demás sesiones fueron cerradas.',
                'success'
            );
        } catch (err) {
            showToast(err?.message || 'No fue posible actualizar la contraseña.', 'error');
        } finally {
            setCambiandoPwd(false);
        }
    };

    const anteriorTipo = idEditando ? tipos.find((t) => t.id === idEditando) : null;

    return html`
        <div class="spa-view-enter">
            <div class="row g-4">
                <div
                    class=${admin ? 'col-md-5' : 'col-md-6 parq-center-card'}
                    id="col-left-config"
                >
                    ${admin
                        ? html`
                              <div class="parq-card parq-card-accent-amber mb-4" id="card-form-tipo">
                                  <div class="parq-card-header">
                                      <span>Tipo de Vehículo y Tarifas</span>
                                      <span class="parq-badge parq-badge-amber">Solo Admin</span>
                                  </div>
                                  <div class="parq-card-body">
                                      <form id="form-tipo" onSubmit=${handleSubmitTipo}>
                                          <div class="mb-3">
                                              <label class="parq-label" for="nombre">Nombre de la Categoría</label>
                                              <input
                                                  type="text"
                                                  id="nombre"
                                                  class="parq-input"
                                                  placeholder="EJ: MOTO, CARRO, CAMIONETA"
                                                  value=${nombreTarifa}
                                                  onInput=${(e) =>
                                                      setNombreTarifa(
                                                          e.target.value.toUpperCase().replace(/[^A-ZÑ\s]/g, '')
                                                      )}
                                                  required
                                              />
                                          </div>
                                          <div class="mb-3">
                                              <label class="parq-label" for="t_hora">Tarifa Hora ($)</label>
                                              <input
                                                  type="number"
                                                  id="t_hora"
                                                  class="parq-input"
                                                  min="0"
                                                  value=${tHora}
                                                  onInput=${(e) => setTHora(e.target.value)}
                                                  required
                                              />
                                          </div>
                                          <div class="mb-3">
                                              <label class="parq-label" for="t_dia">Tarifa Día (12h) ($)</label>
                                              <input
                                                  type="number"
                                                  id="t_dia"
                                                  class="parq-input"
                                                  min="0"
                                                  value=${tDia}
                                                  onInput=${(e) => setTDia(e.target.value)}
                                                  required
                                              />
                                          </div>
                                          <div class="mb-4">
                                              <label class="parq-label" for="t_noche">Tarifa Noche ($)</label>
                                              <input
                                                  type="number"
                                                  id="t_noche"
                                                  class="parq-input"
                                                  min="0"
                                                  value=${tNoche}
                                                  onInput=${(e) => setTNoche(e.target.value)}
                                                  required
                                              />
                                          </div>
                                          <button
                                              type="submit"
                                              id="btn-guardar"
                                              class=${`btn-parq ${idEditando ? 'btn-parq-amber' : 'btn-parq-sage'} w-100 mb-2`}
                                              disabled=${guardandoTarifa}
                                          >
                                              ${idEditando
                                                  ? '⚠️ Revisar y Actualizar Tarifa'
                                                  : 'Guardar Tipo de Vehículo'}
                                          </button>
                                          ${idEditando
                                              ? html`
                                                    <button
                                                        type="button"
                                                        id="btn-cancelar"
                                                        class="btn-parq btn-parq-outline w-100"
                                                        onClick=${cancelarEdicion}
                                                    >
                                                        Cancelar Edición
                                                    </button>
                                                `
                                              : null}
                                      </form>
                                  </div>
                              </div>
                          `
                        : null}

                    <!-- Cambio de Contraseña (Cajero y Admin) -->
                    <div class="parq-card parq-card-accent-sage" id="card-password">
                        <div class="parq-card-header">
                            <span>Seguridad — Cambiar Contraseña</span>
                            <span class="parq-badge parq-badge-sage">Cuenta Activa</span>
                        </div>
                        <div class="parq-card-body">
                            <form id="form-cambiar-password" onSubmit=${handleCambiarPassword}>
                                <div class="mb-3">
                                    <label class="parq-label" for="pwd-actual">Contraseña Actual</label>
                                    <input
                                        type="password"
                                        id="pwd-actual"
                                        class="parq-input"
                                        autocomplete="current-password"
                                        value=${pwdActual}
                                        onInput=${(e) => setPwdActual(e.target.value)}
                                        required
                                    />
                                </div>
                                <div class="mb-3">
                                    <label class="parq-label" for="pwd-nueva">Nueva Contraseña (mín. 4 caracteres)</label>
                                    <input
                                        type="password"
                                        id="pwd-nueva"
                                        class="parq-input"
                                        autocomplete="new-password"
                                        minlength="4"
                                        value=${pwdNueva}
                                        onInput=${(e) => setPwdNueva(e.target.value)}
                                        required
                                    />
                                </div>
                                <div class="mb-4">
                                    <label class="parq-label" for="pwd-confirmar">Confirmar Nueva Contraseña</label>
                                    <input
                                        type="password"
                                        id="pwd-confirmar"
                                        class="parq-input"
                                        autocomplete="new-password"
                                        minlength="4"
                                        value=${pwdConfirmar}
                                        onInput=${(e) => setPwdConfirmar(e.target.value)}
                                        required
                                    />
                                </div>
                                <button
                                    type="submit"
                                    id="btn-password-submit"
                                    class="btn-parq btn-parq-sage w-100"
                                    disabled=${cambiandoPwd}
                                >
                                    ${cambiandoPwd ? 'Actualizando...' : 'Actualizar Contraseña'}
                                </button>
                            </form>
                        </div>
                    </div>
                </div>

                ${admin
                    ? html`
                          <div class="col-md-7" id="col-tarifas-admin">
                              <div class="parq-card">
                                  <div class="parq-card-header">
                                      <span>Tarifas Configuradas</span>
                                      <span class="parq-badge parq-badge-slate">Auditoría Activa</span>
                                  </div>
                                  <div class="parq-table-wrap">
                                      <table class="parq-table">
                                          <thead>
                                              <tr>
                                                  <th>Tipo</th>
                                                  <th>Hora</th>
                                                  <th>Día (12h)</th>
                                                  <th>Noche</th>
                                                  <th>Acción</th>
                                              </tr>
                                          </thead>
                                          <tbody id="lista-tipos">
                                              ${loadingTipos && !tipos.length
                                                  ? [0, 1, 2].map(
                                                        (idx) => html`
                                                            <tr key=${idx}>
                                                                <td><span class="parq-skeleton parq-skeleton-text" style="width: 90px;"></span></td>
                                                                <td><span class="parq-skeleton parq-skeleton-text" style="width: 65px;"></span></td>
                                                                <td><span class="parq-skeleton parq-skeleton-text" style="width: 65px;"></span></td>
                                                                <td><span class="parq-skeleton parq-skeleton-text" style="width: 65px;"></span></td>
                                                                <td><span class="parq-skeleton parq-skeleton-btn"></span></td>
                                                            </tr>
                                                        `
                                                    )
                                                  : tipos.map(
                                                        (t) => html`
                                                            <tr key=${t.id}>
                                                                <td style="font-weight: 700;">${t.nombre}</td>
                                                                <td>${formatMoney(t.tarifa_hora)}</td>
                                                                <td>${formatMoney(t.tarifa_dia)}</td>
                                                                <td>${formatMoney(t.tarifa_noche)}</td>
                                                                <td>
                                                                    <button
                                                                        type="button"
                                                                        class="btn-parq btn-parq-outline btn-parq-sm"
                                                                        onClick=${() => iniciarEdicion(t)}
                                                                    >
                                                                        ✏️ Editar Tarifa
                                                                    </button>
                                                                </td>
                                                            </tr>
                                                        `
                                                    )}
                                          </tbody>
                                      </table>
                                  </div>
                              </div>
                          </div>
                      `
                    : null}
            </div>

            <${Modal}
                id="modalConfirmarTarifa"
                variant="warning-amber"
                isOpen=${Boolean(pendingPayload)}
                onClose=${() => !guardandoTarifa && setPendingPayload(null)}
                title=${html`⚠️ Advertencia: Modificación de Tarifa${' '}
                    <span id="warn-tarifa-nombre">${pendingPayload?.nombre || ''}</span>`}
                footer=${html`
                    <button
                        type="button"
                        class="btn-parq btn-parq-outline"
                        disabled=${guardandoTarifa}
                        onClick=${() => setPendingPayload(null)}
                    >
                        Cancelar
                    </button>
                    <button
                        type="button"
                        class="btn-parq btn-parq-amber"
                        id="btn-confirmar-tarifa-modal"
                        disabled=${guardandoTarifa}
                        onClick=${confirmarActualizacionTarifa}
                    >
                        ${guardandoTarifa ? 'Guardando...' : '⚠️ Sí, Actualizar Tarifa'}
                    </button>
                `}
            >
                <div class="parq-modal-body">
                    <div class="parq-alert-banner alert-amber">
                        <span class="parq-alert-icon" aria-hidden="true">⚠️</span>
                        <div>
                            <strong>Cambio sensible en tarifas del parqueadero:</strong> Los nuevos cobros
                            aplicarán de inmediato a las próximas liquidaciones y la acción quedará grabada en
                            <strong>Auditoría</strong>.
                        </div>
                    </div>
                    <div
                        class="p-3"
                        style="background: var(--surface-subtle); border-radius: var(--radius-md); border: 1px solid var(--border-subtle);"
                        id="warn-tarifa-resumen"
                    >
                        ${pendingPayload
                            ? html`
                                  <div class="mb-1"><strong>Categoría:</strong> ${pendingPayload.nombre}</div>
                                  <div class="mb-1">
                                      <strong>Tarifa Hora:</strong>${' '}
                                      ${anteriorTipo ? formatMoney(anteriorTipo.tarifa_hora) : '—'} →${' '}
                                      <strong>${formatMoney(pendingPayload.tarifa_hora)}</strong>
                                  </div>
                                  <div class="mb-1">
                                      <strong>Tarifa Día:</strong>${' '}
                                      ${anteriorTipo ? formatMoney(anteriorTipo.tarifa_dia) : '—'} →${' '}
                                      <strong>${formatMoney(pendingPayload.tarifa_dia)}</strong>
                                  </div>
                                  <div>
                                      <strong>Tarifa Noche:</strong>${' '}
                                      ${anteriorTipo ? formatMoney(anteriorTipo.tarifa_noche) : '—'} →${' '}
                                      <strong>${formatMoney(pendingPayload.tarifa_noche)}</strong>
                                  </div>
                              `
                            : null}
                    </div>
                </div>
            </${Modal}>
        </div>
    `;
}
