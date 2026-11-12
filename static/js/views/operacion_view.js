// Vista SPA de operación vehicular (recepción de ingreso y liquidación de salida)
import { useEffect, useState } from '../../vendor/hooks.mjs';
import { html } from '../../vendor/htm-preact.mjs';
import { apiRequest } from '../api.js';
import { Modal } from '../components/modal.js';
import {
    ensureTiposLoaded,
    openTicketPreview,
    showToast,
    tiposLoading,
    tiposVehiculo,
} from '../store/app_store.js';
import { prependTicketInStore, updateTicketInStore } from '../store/registros_store.js';
import { formatMoney, sanitizePlaca } from '../ui/format.js';

export function OperacionView() {
    const [placa, setPlaca] = useState('');
    const [idTipoVehiculo, setIdTipoVehiculo] = useState('');
    const [submittingIngreso, setSubmittingIngreso] = useState(false);

    const [identificadorSalida, setIdentificadorSalida] = useState('');
    const [searchingSalida, setSearchingSalida] = useState(false);
    const [ticketPreSalida, setTicketPreSalida] = useState(null);
    const [usarPersonalizado, setUsarPersonalizado] = useState(false);
    const [valorPersonalizado, setValorPersonalizado] = useState('');
    const [motivoAjuste, setMotivoAjuste] = useState('');
    const [confirmandoSalida, setConfirmandoSalida] = useState(false);

    const tipos = tiposVehiculo.value;
    const loadingTipos = tiposLoading.value;

    useEffect(() => {
        ensureTiposLoaded().catch((err) => {
            showToast(err?.message || 'Error al cargar tarifas de vehículos.', 'error');
        });
    }, []);

    useEffect(() => {
        if (tipos.length > 0 && !tipos.some((t) => t.id === idTipoVehiculo)) {
            setIdTipoVehiculo(tipos[0].id);
        }
    }, [tipos]);

    const handleIngreso = async (e) => {
        e.preventDefault();
        const cleanPlaca = sanitizePlaca(placa).trim();
        if (!cleanPlaca || !idTipoVehiculo) {
            showToast('Complete placa y tipo de vehículo.', 'warning');
            return;
        }

        setSubmittingIngreso(true);
        try {
            const data = await apiRequest('/ticket/ingreso', {
                method: 'POST',
                body: { placa: cleanPlaca, id_tipo_vehiculo: idTipoVehiculo },
            });
            setPlaca('');
            prependTicketInStore(data);
            showToast(`Ingreso registrado para ${data.placa}.`, 'success');
            openTicketPreview(data, 'ingreso');
        } catch (err) {
            showToast(err?.message || 'Error al registrar ingreso.', 'error');
        } finally {
            setSubmittingIngreso(false);
        }
    };

    const handleBuscarSalida = async (e) => {
        e.preventDefault();
        const query = identificadorSalida.trim().toUpperCase();
        if (!query) return;

        setSearchingSalida(true);
        try {
            const data = await apiRequest(`/ticket/pre-salida/${encodeURIComponent(query)}`);
            setTicketPreSalida(data);
            setUsarPersonalizado(false);
            setValorPersonalizado('');
            setMotivoAjuste('');
        } catch (err) {
            showToast(err?.message || 'No se encontró ticket activo.', 'warning');
        } finally {
            setSearchingSalida(false);
        }
    };

    const handleConfirmarSalida = async () => {
        if (!ticketPreSalida) return;

        const payload = {};
        if (usarPersonalizado && String(valorPersonalizado).trim() !== '') {
            const motivo = motivoAjuste.trim();
            if (!motivo) {
                showToast('Debe indicar el motivo del ajuste de precio.', 'warning');
                return;
            }
            payload.precio_personalizado = parseFloat(valorPersonalizado);
            payload.motivo_ajuste = motivo;
        }

        setConfirmandoSalida(true);
        try {
            const data = await apiRequest(`/ticket/salida/${encodeURIComponent(ticketPreSalida.id)}`, {
                method: 'PUT',
                body: payload,
            });
            updateTicketInStore(data);
            setTicketPreSalida(null);
            setIdentificadorSalida('');
            showToast(`Salida liquidada para ${data.placa}.`, 'success');
            openTicketPreview(data, 'salida');
        } catch (err) {
            showToast(err?.message || 'Error al registrar salida.', 'error');
        } finally {
            setConfirmandoSalida(false);
        }
    };

    return html`
        <div class="spa-view-enter">
            <div class="row g-4">
                <!-- INGRESO -->
                <div class="col-md-6">
                    <div class="parq-card parq-card-accent-sage h-100">
                        <div class="parq-card-header">
                            <span>ENTRADA (Ingreso de Vehículo)</span>
                            <span class="parq-badge parq-badge-sage">Recepción</span>
                        </div>
                        <div class="parq-card-body">
                            <form id="form-ingreso" onSubmit=${handleIngreso}>
                                <div class="mb-3">
                                    <label class="parq-label" for="placa">Placa del Vehículo</label>
                                    <input
                                        type="text"
                                        id="placa"
                                        class="parq-input parq-input-placa"
                                        placeholder="ABC123"
                                        value=${placa}
                                        onInput=${(e) => setPlaca(sanitizePlaca(e.target.value))}
                                        required
                                    />
                                </div>
                                <div class="mb-4">
                                    <label class="parq-label" for="select-tipo">Tipo de Vehículo y Tarifa</label>
                                    <select
                                        id="select-tipo"
                                        class="parq-select"
                                        value=${idTipoVehiculo}
                                        disabled=${loadingTipos && !tipos.length}
                                        onChange=${(e) => setIdTipoVehiculo(e.target.value)}
                                        required
                                    >
                                        ${!tipos.length
                                            ? html`<option value="">
                                                  ${loadingTipos ? 'Cargando tarifas...' : 'Sin tipos registrados'}
                                              </option>`
                                            : tipos.map(
                                                  (t) => html`
                                                      <option key=${t.id} value=${t.id}>
                                                          ${t.nombre} (${formatMoney(t.tarifa_hora)}/h)
                                                      </option>
                                                  `
                                              )}
                                    </select>
                                </div>
                                <button
                                    type="submit"
                                    class="btn-parq btn-parq-sage btn-parq-lg w-100"
                                    disabled=${submittingIngreso || !tipos.length}
                                >
                                    ${submittingIngreso ? 'Registrando...' : 'Generar Ingreso e Imprimir'}
                                </button>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- SALIDA -->
                <div class="col-md-6">
                    <div class="parq-card parq-card-accent-amber h-100">
                        <div class="parq-card-header">
                            <span>SALIDA Y LIQUIDACIÓN</span>
                            <span class="parq-badge parq-badge-amber">Caja</span>
                        </div>
                        <div class="parq-card-body">
                            <form id="form-pre-salida" onSubmit=${handleBuscarSalida}>
                                <div class="mb-4">
                                    <label class="parq-label" for="id-ticket">ID del Ticket o Placa</label>
                                    <input
                                        type="text"
                                        id="id-ticket"
                                        class="parq-input parq-input-placa"
                                        placeholder="PLACA O ID DE TICKET"
                                        value=${identificadorSalida}
                                        onInput=${(e) => setIdentificadorSalida(e.target.value.toUpperCase())}
                                        required
                                    />
                                </div>
                                <button
                                    type="submit"
                                    class="btn-parq btn-parq-amber btn-parq-lg w-100"
                                    disabled=${searchingSalida}
                                >
                                    ${searchingSalida ? 'Buscando...' : '🔍 Buscar y Liquidar'}
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <${Modal}
                id="modalLiquidacion"
                isOpen=${Boolean(ticketPreSalida)}
                onClose=${() => !confirmandoSalida && setTicketPreSalida(null)}
                title=${html`Confirmar Salida — Placa${' '}
                    <span id="mod-placa" class="parq-placa-cell">${ticketPreSalida?.placa || ''}</span>`}
                footer=${html`
                    <button
                        type="button"
                        class="btn-parq btn-parq-outline"
                        disabled=${confirmandoSalida}
                        onClick=${() => setTicketPreSalida(null)}
                    >
                        Cancelar
                    </button>
                    <button
                        type="button"
                        class="btn-parq btn-parq-sage"
                        id="btn-confirmar-salida"
                        disabled=${confirmandoSalida}
                        onClick=${handleConfirmarSalida}
                    >
                        ${confirmandoSalida ? 'Liquidando...' : 'Confirmar y Cobrar'}
                    </button>
                `}
            >
                <div class="parq-modal-body">
                    <div class="parq-summary-box">
                        <div class="small" style="color: var(--text-secondary);">
                            Tiempo facturado: <strong><span id="mod-horas">${ticketPreSalida?.total_horas ?? 0}</span> Horas</strong>
                        </div>
                        <div class="parq-summary-amount" id="mod-total">
                            ${formatMoney(ticketPreSalida?.precio_total ?? 0)}
                        </div>
                        <div class="small" style="color: var(--text-muted);">Tarifa calculada por el sistema</div>
                    </div>

                    <div class="form-check mb-3">
                        <input
                            type="checkbox"
                            class="form-check-input"
                            id="check-personalizado"
                            checked=${usarPersonalizado}
                            onChange=${(e) => setUsarPersonalizado(e.target.checked)}
                        />
                        <label class="form-check-label" for="check-personalizado">
                            Modificar valor a cobrar manualmente (requiere motivo para auditoría)
                        </label>
                    </div>

                    ${usarPersonalizado
                        ? html`
                              <div id="div-personalizado">
                                  <div class="mb-3">
                                      <label class="parq-label" for="valor-personalizado">
                                          Nuevo valor final a cobrar ($)
                                      </label>
                                      <input
                                          type="number"
                                          id="valor-personalizado"
                                          class="parq-input"
                                          placeholder="¿Cuánto vas a cobrar?"
                                          min="0"
                                          step="50"
                                          value=${valorPersonalizado}
                                          onInput=${(e) => setValorPersonalizado(e.target.value)}
                                      />
                                  </div>
                                  <div>
                                      <label class="parq-label" for="motivo-ajuste">Motivo del ajuste</label>
                                      <input
                                          type="text"
                                          id="motivo-ajuste"
                                          class="parq-input"
                                          placeholder="Ej. Convenio comercial, cliente frecuente..."
                                          value=${motivoAjuste}
                                          onInput=${(e) => setMotivoAjuste(e.target.value)}
                                      />
                                  </div>
                              </div>
                          `
                        : null}
                </div>
            </${Modal}>
        </div>
    `;
}
