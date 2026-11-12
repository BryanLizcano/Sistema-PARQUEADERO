// Vista SPA de historial paginado, exportación streaming (solo Admin) y modales auditados
import { useEffect, useMemo, useState } from '../../vendor/hooks.mjs';
import { html } from '../../vendor/htm-preact.mjs';
import { apiRequest } from '../api.js';
import { Modal } from '../components/modal.js';
import { getLocalTodayISO, PeriodPicker } from '../components/period_picker.js';
import {
    ensureTiposLoaded,
    isAdmin,
    isOnline,
    openTicketPreview,
    showToast,
    tiposVehiculo,
} from '../store/app_store.js';
import {
    availableYears,
    debounce,
    filtroEstado,
    filtroPlaca,
    kpiStats,
    loadExportYears,
    loadRegistros,
    PAGE_LIMIT,
    registros,
    registrosError,
    registrosLoaded,
    registrosLoading,
    registrosPage,
    registrosPerfMs,
    registrosStale,
    registrosTotal,
    registrosTotalPages,
    removeTicketFromStore,
    updateTicketInStore,
    validateExportRange,
} from '../store/registros_store.js';
import {
    formatDateTime,
    formatMoney,
    formatNullableMoney,
    sanitizePlaca,
} from '../ui/format.js';

export function RegistrosView() {
    const admin = isAdmin.value;
    const online = isOnline.value;
    const rows = registros.value;
    const page = registrosPage.value;
    const total = registrosTotal.value;
    const totalPages = registrosTotalPages.value;
    const loading = registrosLoading.value;
    const loaded = registrosLoaded.value;
    const errorState = registrosError.value;
    const perfMs = registrosPerfMs.value;
    const kpi = kpiStats.value;
    const yearsList = availableYears.value;
    const tipos = tiposVehiculo.value;

    // Estado de exportación (Solo Admin)
    const todayISO = useMemo(() => getLocalTodayISO(), []);
    const [expFormato, setExpFormato] = useState('xlsx');
    const [expTipo, setExpTipo] = useState('dias');
    const [expDesde, setExpDesde] = useState(todayISO);
    const [expHasta, setExpHasta] = useState(todayISO);
    const [exporting, setExporting] = useState(false);

    // Modales de operación sobre tickets
    const [ticketAjuste, setTicketAjuste] = useState(null);
    const [ajustePrecioFinal, setAjustePrecioFinal] = useState('');
    const [ajusteMotivo, setAjusteMotivo] = useState('');
    const [savingAjuste, setSavingAjuste] = useState(false);

    const [ticketEdicion, setTicketEdicion] = useState(null);
    const [editPlaca, setEditPlaca] = useState('');
    const [editTipoId, setEditTipoId] = useState('');
    const [editEstado, setEditEstado] = useState('ACTIVO');
    const [editPrecioFinal, setEditPrecioFinal] = useState('');
    const [editMotivo, setEditMotivo] = useState('');
    const [savingEdicion, setSavingEdicion] = useState(false);

    const [ticketEliminar, setTicketEliminar] = useState(null);
    const [delConfirmWord, setDelConfirmWord] = useState('');
    const [savingEliminar, setSavingEliminar] = useState(false);

    useEffect(() => {
        if (!loaded) {
            loadRegistros(1, { showSkeleton: true });
        } else if (registrosStale.value) {
            loadRegistros(registrosPage.value, { background: true });
        }
    }, []);

    useEffect(() => {
        if (admin) {
            loadExportYears();
        }
    }, [admin]);

    useEffect(() => {
        if (online && errorState) {
            loadRegistros(registrosPage.value);
        }
    }, [online]);

    const triggerDebouncedFilter = useMemo(
        () => debounce(() => loadRegistros(1), 220),
        []
    );

    const handleTipoExportChange = (nextTipo) => {
        setExpTipo(nextTipo);
        if (nextTipo === 'dias') {
            const today = getLocalTodayISO();
            setExpDesde(today);
            setExpHasta(today);
        } else if (nextTipo === 'semanas') {
            setExpDesde('');
            setExpHasta('');
        }
    };

    const validation = validateExportRange(expTipo, expDesde, expHasta);

    const handleExportSubmit = async (e) => {
        e.preventDefault();
        if (!admin) return;
        if (!validation.valid) {
            showToast(validation.message, 'warning');
            return;
        }

        setExporting(true);
        const params = new URLSearchParams({
            formato: expFormato,
            tipo: expTipo,
            desde: expDesde,
            hasta: expHasta,
        });

        try {
            const response = await fetch(`/api/exportar?${params.toString()}`, {
                credentials: 'same-origin',
            });
            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                throw new Error(payload?.error?.mensaje || 'Error al exportar reporte.');
            }

            let filename = `reporte_${expTipo}_${expDesde}_a_${expHasta}.${expFormato}`;
            const disposition = response.headers.get('content-disposition') || '';
            const match = /filename="?([^";]+)"?/i.exec(disposition);
            if (match && match[1]) {
                filename = match[1];
            }

            const blob = await response.blob();
            const downloadUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = filename;
            a.setAttribute('data-no-transition', 'true');
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();

            // Diferir limpieza del blob URL para que Firefox/Zen complete la descarga sin errores
            window.setTimeout(() => {
                a.remove();
                URL.revokeObjectURL(downloadUrl);
            }, 15000);

            showToast(
                `Reporte ${expFormato.toUpperCase()} (${validation.days} días) descargado con éxito.`,
                'success'
            );
        } catch (err) {
            showToast(err?.message || 'No fue posible exportar el reporte.', 'error');
        } finally {
            setExporting(false);
        }
    };

    const abrirModalAjuste = (ticket) => {
        const calculado = ticket.precio_calculado ?? ticket.precio_total ?? ticket.precio_final ?? 0;
        const actual = ticket.precio_final ?? ticket.precio_total ?? calculado ?? 0;
        setTicketAjuste(ticket);
        setAjustePrecioFinal(String(actual));
        setAjusteMotivo(ticket.motivo_ajuste || '');
    };

    const handleSubmitAjuste = async (e) => {
        e.preventDefault();
        if (!ticketAjuste) return;

        const precio_final = parseFloat(ajustePrecioFinal);
        const motivo_ajuste = ajusteMotivo.trim();
        if (Number.isNaN(precio_final) || precio_final < 0 || !motivo_ajuste) {
            showToast('Ingrese un precio válido y el motivo obligatorio del ajuste.', 'warning');
            return;
        }

        setSavingAjuste(true);
        try {
            const updated = await apiRequest(`/ticket/${encodeURIComponent(ticketAjuste.id)}/precio`, {
                method: 'PATCH',
                body: { precio_final, motivo_ajuste },
            });
            updateTicketInStore(updated);
            setTicketAjuste(null);
            showToast(`Precio final ajustado para ${ticketAjuste.placa}.`, 'success');
        } catch (err) {
            showToast(err?.message || 'Error al ajustar el precio.', 'error');
        } finally {
            setSavingAjuste(false);
        }
    };

    const abrirModalEditar = async (ticket) => {
        setTicketEdicion(ticket);
        setEditPlaca(ticket.placa);
        setEditTipoId(ticket.id_tipo_vehiculo || '');
        setEditEstado(ticket.fecha_salida || ticket.estado === 'FINALIZADO' ? 'FINALIZADO' : 'ACTIVO');
        setEditPrecioFinal(
            ticket.precio_final !== null && ticket.precio_final !== undefined
                ? String(ticket.precio_final)
                : ticket.precio_total !== null && ticket.precio_total !== undefined
                ? String(ticket.precio_total)
                : ''
        );
        setEditMotivo(ticket.motivo_ajuste || '');

        if (!tiposVehiculo.value.length) {
            await ensureTiposLoaded().catch(() => {});
        }
    };

    const handleSubmitEditar = async (e) => {
        e.preventDefault();
        if (!ticketEdicion) return;

        const placaClean = sanitizePlaca(editPlaca).trim();
        const motivoClean = editMotivo.trim();
        if (!placaClean || !editTipoId || !motivoClean) {
            showToast('Complete la placa, tipo de vehículo y el motivo obligatorio de edición.', 'warning');
            return;
        }

        const payload = {
            placa: placaClean,
            id_tipo_vehiculo: editTipoId,
            estado: editEstado,
            motivo_ajuste: motivoClean,
        };
        if (String(editPrecioFinal).trim() !== '') {
            payload.precio_final = parseFloat(editPrecioFinal);
        }

        setSavingEdicion(true);
        try {
            const updated = await apiRequest(`/ticket/${encodeURIComponent(ticketEdicion.id)}`, {
                method: 'PUT',
                body: payload,
            });
            updateTicketInStore(updated);
            setTicketEdicion(null);
            showToast(`Ticket ${placaClean} actualizado y registrado en auditoría.`, 'success');
        } catch (err) {
            showToast(err?.message || 'No fue posible editar el ticket.', 'error');
        } finally {
            setSavingEdicion(false);
        }
    };

    const abrirModalEliminar = (ticket) => {
        setTicketEliminar(ticket);
        setDelConfirmWord('');
    };

    const handleSubmitEliminar = async (e) => {
        e.preventDefault();
        if (!ticketEliminar) return;
        if (delConfirmWord.trim().toUpperCase() !== 'ELIMINAR') {
            showToast('Debe escribir exactamente ELIMINAR para confirmar.', 'warning');
            return;
        }

        setSavingEliminar(true);
        try {
            await apiRequest(`/ticket/${encodeURIComponent(ticketEliminar.id)}`, {
                method: 'DELETE',
            });
            removeTicketFromStore(ticketEliminar.id);
            showToast(
                `Ticket ${ticketEliminar.placa} eliminado lógicamente (registrado en auditoría).`,
                'warning'
            );
            setTicketEliminar(null);
        } catch (err) {
            showToast(err?.message || 'No fue posible eliminar el registro.', 'error');
        } finally {
            setSavingEliminar(false);
        }
    };

    const handleImprimir = (ticket) => {
        const tipoImpresion = ticket.fecha_salida || ticket.estado === 'FINALIZADO' ? 'salida' : 'ingreso';
        openTicketPreview(ticket, tipoImpresion);
    };

    const startRow = total > 0 ? (page - 1) * PAGE_LIMIT + 1 : 0;
    const endRow = total > 0 ? Math.min(page * PAGE_LIMIT, total) : 0;
    const isOfflineMode = !online || errorState?.status === 0;

    return html`
        <div class="spa-view-enter">
            <!-- Banner de estado sin conexión -->
            <div
                class=${`parq-offline-banner ${!online ? 'is-visible' : ''}`}
                id="offline-banner"
                role="alert"
            >
                <span>⚠️ Sin conexión con el servidor local. Algunos datos podrían no estar actualizados.</span>
                <button
                    type="button"
                    class="btn-parq btn-parq-outline btn-parq-sm"
                    id="btn-offline-retry"
                    onClick=${() => loadRegistros(page, { showSkeleton: true })}
                >
                    Reintentar
                </button>
            </div>

            <!-- Tarjetas KPI de la página actual -->
            <div class="row g-3 mb-4">
                <div class="col-md-4">
                    <div class="parq-kpi-card">
                        <div class="parq-kpi-label">Total Registros (Filtro)</div>
                        <div class="parq-kpi-value" id="kpi-total">
                            ${loading && !loaded
                                ? html`<span class="parq-skeleton parq-skeleton-kpi" aria-hidden="true"></span>`
                                : Number(total || 0).toLocaleString()}
                        </div>
                        <div class="parq-kpi-sub" id="kpi-rango-sub">
                            ${total > 0 ? `Mostrando ${startRow}–${endRow} de ${total}` : 'Sin coincidencias activas'}
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="parq-kpi-card">
                        <div class="parq-kpi-label">Activos en Página</div>
                        <div class="parq-kpi-value" id="kpi-activos">
                            ${loading && !loaded
                                ? html`<span class="parq-skeleton parq-skeleton-kpi" aria-hidden="true"></span>`
                                : String(kpi.activos)}
                        </div>
                        <div class="parq-kpi-sub">Vehículos actualmente en parqueadero</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="parq-kpi-card">
                        <div class="parq-kpi-label">Finalizados / Recaudo Página</div>
                        <div class="parq-kpi-value" id="kpi-recaudo">
                            ${loading && !loaded
                                ? html`<span class="parq-skeleton parq-skeleton-kpi" aria-hidden="true"></span>`
                                : formatMoney(kpi.recaudo)}
                        </div>
                        <div class="parq-kpi-sub" id="kpi-finalizados-sub">
                            ${kpi.finalizados} finalizados en esta página
                        </div>
                    </div>
                </div>
            </div>

            <!-- Panel de Exportación Streaming (Visible SOLO para Administrador) -->
            ${admin
                ? html`
                      <div class="parq-card parq-card-accent-slate mb-4 parq-card-overflow-visible" id="card-exportar-admin">
                          <div class="parq-card-header">
                              <span>Exportar Reportes Contables (Streaming Bajo Consumo)</span>
                              <span class="parq-badge parq-badge-amber">Solo Administrador</span>
                          </div>
                          <div class="parq-card-body">
                              <form id="form-exportar" class="row g-3 align-items-end" onSubmit=${handleExportSubmit}>
                                  <div class="col-md-2">
                                      <label class="parq-label" for="exp-formato">Formato</label>
                                      <select
                                          id="exp-formato"
                                          class="parq-select"
                                          value=${expFormato}
                                          onChange=${(e) => setExpFormato(e.target.value)}
                                      >
                                          <option value="xlsx">Excel (.xlsx)</option>
                                          <option value="pdf">PDF (.pdf)</option>
                                      </select>
                                  </div>
                                  <div class="col-md-3">
                                      <label class="parq-label" for="exp-tipo">Rango (Límite Estricto)</label>
                                      <select
                                          id="exp-tipo"
                                          class="parq-select"
                                          value=${expTipo}
                                          onChange=${(e) => handleTipoExportChange(e.target.value)}
                                      >
                                          <option value="dias">Días (máx. 20 días)</option>
                                          <option value="semanas">Semanas (máx. 10 sem.)</option>
                                          <option value="mes">Mes completo (1 mes)</option>
                                          <option value="anio">Año completo (1 año)</option>
                                      </select>
                                  </div>

                                  <div class="col-md-4">
                                      <${PeriodPicker}
                                          tipo=${expTipo}
                                          desde=${expDesde}
                                          hasta=${expHasta}
                                          availableYears=${yearsList}
                                          onRangeChange=${({ desde, hasta }) => {
                                              setExpDesde(desde);
                                              setExpHasta(hasta);
                                          }}
                                      />
                                  </div>

                                  <div class="col-md-3">
                                      <button
                                          type="submit"
                                          id="btn-exportar-submit"
                                          class="btn-parq btn-parq-slate w-100"
                                          disabled=${exporting || !validation.valid}
                                      >
                                          ${exporting ? '⏳ Generando stream...' : '⬇️ Descargar Reporte'}
                                      </button>
                                  </div>
                              </form>

                              <div
                                  class=${`parq-export-feedback ${
                                      exporting
                                          ? 'is-downloading'
                                          : validation.valid
                                          ? 'is-valid'
                                          : 'is-invalid'
                                  }`}
                                  id="export-feedback"
                                  role="status"
                                  aria-live="polite"
                              >
                                  <span id="export-feedback-text">
                                      ${exporting
                                          ? `⏳ Generando archivo ${expFormato.toUpperCase()} en modo streaming...`
                                          : validation.message}
                                  </span>
                                  <span class="small" id="export-limit-badge">${validation.ruleLabel}</span>
                              </div>
                          </div>
                      </div>
                  `
                : null}

            <!-- Tabla de Historial Paginado (50 por página) -->
            <div class="parq-card parq-card-accent-sage">
                <div class="parq-card-header">
                    <span>Historial de Vehículos</span>
                    <div class="d-flex align-items-center gap-2">
                        <span
                            class="parq-badge parq-badge-sage"
                            id="badge-perf"
                            title="Tiempo de respuesta y renderizado"
                        >
                            ${perfMs !== null ? `⚡ ${perfMs} ms` : '⚡ < 300 ms'}
                        </span>
                        <span class="parq-badge parq-badge-slate">50 por página</span>
                    </div>
                </div>

                <form
                    id="form-filtros"
                    class="parq-filter-bar"
                    role="search"
                    onSubmit=${(e) => {
                        e.preventDefault();
                        loadRegistros(1);
                    }}
                >
                    <div style="min-width: 210px; flex: 1;">
                        <label class="parq-label" for="filtro-placa">
                            Buscar por Placa (búsqueda automática)
                        </label>
                        <input
                            type="text"
                            id="filtro-placa"
                            class="parq-input"
                            placeholder="Ej. ABC123"
                            autocomplete="off"
                            value=${filtroPlaca.value}
                            onInput=${(e) => {
                                filtroPlaca.value = sanitizePlaca(e.target.value);
                                triggerDebouncedFilter();
                            }}
                        />
                    </div>
                    <div style="min-width: 190px;">
                        <label class="parq-label" for="filtro-estado">Estado</label>
                        <select
                            id="filtro-estado"
                            class="parq-select"
                            value=${filtroEstado.value}
                            onChange=${(e) => {
                                filtroEstado.value = e.target.value;
                                triggerDebouncedFilter();
                            }}
                        >
                            <option value="">Todos los estados</option>
                            <option value="ACTIVO">Activos en parqueadero</option>
                            <option value="FINALIZADO">Finalizados</option>
                        </select>
                    </div>
                    <div class="d-flex gap-2">
                        <button type="submit" class="btn-parq btn-parq-sage">Filtrar</button>
                        <button
                            type="button"
                            id="btn-limpiar-filtros"
                            class="btn-parq btn-parq-outline"
                            onClick=${() => {
                                filtroPlaca.value = '';
                                filtroEstado.value = '';
                                showToast('Filtros restablecidos.', 'info', 2500);
                                loadRegistros(1);
                            }}
                        >
                            Limpiar
                        </button>
                    </div>
                </form>

                <div class="parq-table-wrap">
                    <table class="parq-table" aria-live="polite">
                        <thead>
                            <tr>
                                <th>Placa</th>
                                <th>Ingreso</th>
                                <th>Salida</th>
                                <th>Estado</th>
                                <th>Cobro</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody id="lista-tickets">
                            ${loading
                                ? [0, 1, 2, 3, 4, 5].map(
                                      (idx) => html`
                                          <tr key=${`skel-${idx}`}>
                                              <td><span class="parq-skeleton parq-skeleton-text" style="width: 76px;"></span></td>
                                              <td><span class="parq-skeleton parq-skeleton-text" style="width: 135px;"></span></td>
                                              <td><span class="parq-skeleton parq-skeleton-text" style="width: 135px;"></span></td>
                                              <td><span class="parq-skeleton parq-skeleton-badge"></span></td>
                                              <td><span class="parq-skeleton parq-skeleton-text" style="width: 68px;"></span></td>
                                              <td>
                                                  <div class="d-flex gap-2">
                                                      <span class="parq-skeleton parq-skeleton-btn"></span>
                                                      <span class="parq-skeleton parq-skeleton-btn"></span>
                                                  </div>
                                              </td>
                                          </tr>
                                      `
                                  )
                                : errorState
                                ? html`
                                      <tr>
                                          <td colSpan="6">
                                              <div class="parq-state-box state-error">
                                                  <div class="parq-state-icon" aria-hidden="true">
                                                      ${isOfflineMode ? '📡' : '⚠️'}
                                                  </div>
                                                  <div class="parq-state-title">
                                                      ${isOfflineMode
                                                          ? 'Sin conexión con el servidor'
                                                          : 'No se pudo cargar el historial'}
                                                  </div>
                                                  <div class="parq-state-desc">
                                                      ${isOfflineMode
                                                          ? 'Verifique que el servicio local de FastAPI siga activo o la conexión de red.'
                                                          : errorState.message}
                                                  </div>
                                                  <button
                                                      type="button"
                                                      class="btn-parq btn-parq-sage"
                                                      onClick=${() => loadRegistros(page, { showSkeleton: true })}
                                                  >
                                                      Reintentar
                                                  </button>
                                              </div>
                                          </td>
                                      </tr>
                                  `
                                : rows.length === 0
                                ? html`
                                      <tr>
                                          <td colSpan="6">
                                              <div class="parq-state-box state-empty">
                                                  <div class="parq-state-icon" aria-hidden="true">🅿️</div>
                                                  <div class="parq-state-title">Sin registros encontrados</div>
                                                  <div class="parq-state-desc">
                                                      ${filtroPlaca.value || filtroEstado.value
                                                          ? 'No existen tickets que coincidan con los filtros seleccionados.'
                                                          : 'Aún no hay vehículos registrados en el sistema.'}
                                                  </div>
                                                  ${filtroPlaca.value || filtroEstado.value
                                                      ? html`
                                                            <button
                                                                type="button"
                                                                class="btn-parq btn-parq-sage"
                                                                onClick=${() => {
                                                                    filtroPlaca.value = '';
                                                                    filtroEstado.value = '';
                                                                    loadRegistros(1);
                                                                }}
                                                            >
                                                                Limpiar filtros
                                                            </button>
                                                        `
                                                      : null}
                                              </div>
                                          </td>
                                      </tr>
                                  `
                                : rows.map((t) => {
                                      const esFinalizado = Boolean(t.fecha_salida) || t.estado === 'FINALIZADO';
                                      const valorCobro = formatNullableMoney(t.precio_final ?? t.precio_total);

                                      return html`
                                          <tr key=${t.id}>
                                              <td class="parq-placa-cell">${t.placa}</td>
                                              <td>${formatDateTime(t.fecha_ingreso)}</td>
                                              <td>${formatDateTime(t.fecha_salida)}</td>
                                              <td>
                                                  <span class=${`parq-badge ${esFinalizado ? 'parq-badge-slate' : 'parq-badge-sage'}`}>
                                                      ${esFinalizado ? 'Finalizado' : 'Activo'}
                                                  </span>
                                              </td>
                                              <td style="font-weight: 700;">
                                                  ${valorCobro}
                                                  ${t.motivo_ajuste
                                                      ? html`
                                                            <div
                                                                style="font-size: 0.75rem; font-weight: 400; color: var(--text-muted);"
                                                            >
                                                                Ajuste: ${t.motivo_ajuste}
                                                            </div>
                                                        `
                                                      : null}
                                              </td>
                                              <td>
                                                  <div class="d-flex gap-2 flex-wrap">
                                                      <button
                                                          type="button"
                                                          class="btn-parq btn-parq-outline btn-parq-sm"
                                                          title="Imprimir comprobante"
                                                          onClick=${() => handleImprimir(t)}
                                                      >
                                                          🖨️ Imprimir
                                                      </button>
                                                      <button
                                                          type="button"
                                                          class="btn-parq btn-parq-amber btn-parq-sm"
                                                          title="Ajustar precio final con auditoría"
                                                          onClick=${() => abrirModalAjuste(t)}
                                                      >
                                                          💲 Precio
                                                      </button>
                                                      ${admin
                                                          ? html`
                                                                <button
                                                                    type="button"
                                                                    class="btn-parq btn-parq-outline btn-parq-sm"
                                                                    title="Editar ticket (Solo Admin)"
                                                                    onClick=${() => abrirModalEditar(t)}
                                                                >
                                                                    ✏️ Editar
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    class="btn-parq btn-parq-danger btn-parq-sm"
                                                                    title="Eliminar ticket (Solo Admin)"
                                                                    onClick=${() => abrirModalEliminar(t)}
                                                                >
                                                                    🗑️ Eliminar
                                                                </button>
                                                            `
                                                          : null}
                                                  </div>
                                              </td>
                                          </tr>
                                      `;
                                  })}
                        </tbody>
                    </table>
                </div>

                <div class="parq-pagination">
                    <div class="d-flex align-items-center gap-3 flex-wrap">
                        <strong id="paginacion-indicador">Página ${page} de ${totalPages}</strong>
                        <span id="paginacion-total" class="small" style="color: var(--text-muted);">
                            ${Number(total).toLocaleString()} registros totales
                        </span>
                    </div>
                    <div class="d-flex gap-2">
                        <button
                            type="button"
                            id="btn-page-prev"
                            class="btn-parq btn-parq-outline btn-parq-sm"
                            disabled=${page <= 1}
                            onClick=${() => page > 1 && loadRegistros(page - 1)}
                        >
                            ← Anterior
                        </button>
                        <button
                            type="button"
                            id="btn-page-next"
                            class="btn-parq btn-parq-outline btn-parq-sm"
                            disabled=${page >= totalPages}
                            onClick=${() => page < totalPages && loadRegistros(page + 1)}
                        >
                            Siguiente →
                        </button>
                    </div>
                </div>
            </div>

            <!-- Modal 1: Ajuste de Precio Final (Cajero y Admin) -->
            <${Modal}
                id="modalAjustePrecio"
                isOpen=${Boolean(ticketAjuste)}
                onClose=${() => !savingAjuste && setTicketAjuste(null)}
                title=${html`💲 Ajustar Precio Final — Placa${' '}
                    <span id="ajuste-placa" class="parq-placa-cell">${ticketAjuste?.placa || ''}</span>`}
            >
                <form id="form-ajuste-precio" onSubmit=${handleSubmitAjuste}>
                    <div class="parq-modal-body">
                        <div class="parq-summary-box">
                            <div class="small" style="color: var(--text-secondary);">
                                Precio Original Calculado (Inmutable en BD)
                            </div>
                            <div class="parq-summary-amount" id="ajuste-precio-calculado">
                                ${formatMoney(
                                    ticketAjuste?.precio_calculado ??
                                        ticketAjuste?.precio_total ??
                                        ticketAjuste?.precio_final ??
                                        0
                                )}
                            </div>
                            <div class="small" style="color: var(--text-muted);">
                                El ajuste quedará registrado en el historial de auditoría
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="parq-label" for="ajuste-precio-final">Nuevo Precio Final ($)</label>
                            <input
                                type="number"
                                id="ajuste-precio-final"
                                class="parq-input"
                                min="0"
                                step="50"
                                value=${ajustePrecioFinal}
                                onInput=${(e) => setAjustePrecioFinal(e.target.value)}
                                required
                            />
                        </div>
                        <div>
                            <label class="parq-label" for="ajuste-motivo">Motivo del ajuste (Obligatorio)</label>
                            <input
                                type="text"
                                id="ajuste-motivo"
                                class="parq-input"
                                placeholder="Indique la razón del cambio de tarifa"
                                value=${ajusteMotivo}
                                onInput=${(e) => setAjusteMotivo(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    <div class="parq-modal-footer">
                        <button
                            type="button"
                            class="btn-parq btn-parq-outline"
                            disabled=${savingAjuste}
                            onClick=${() => setTicketAjuste(null)}
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            id="btn-ajuste-submit"
                            class="btn-parq btn-parq-sage"
                            disabled=${savingAjuste}
                        >
                            ${savingAjuste ? 'Guardando...' : 'Guardar Ajuste'}
                        </button>
                    </div>
                </form>
            </${Modal}>

            <!-- Modal 2 (Solo Admin): Editar Ticket con Advertencia Ámbar/Roja -->
            <${Modal}
                id="modalEditarTicket"
                variant="warning-amber"
                isOpen=${Boolean(ticketEdicion)}
                onClose=${() => !savingEdicion && setTicketEdicion(null)}
                title=${html`⚠️ Advertencia de Edición Administrativa — Ticket${' '}
                    <span id="edit-ticket-placa" class="parq-placa-cell">${ticketEdicion?.placa || ''}</span>`}
            >
                <form id="form-editar-ticket" onSubmit=${handleSubmitEditar}>
                    <div class="parq-modal-body">
                        <div class="parq-alert-banner alert-amber">
                            <span class="parq-alert-icon" aria-hidden="true">⚠️</span>
                            <div>
                                <strong>Atención Administrador:</strong> Está modificando datos estructurales de un
                                registro operativo. El estado anterior y el nuevo quedarán grabados permanentemente en la
                                tabla de <strong>Auditoría</strong>.
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="parq-label" for="edit-placa">Placa del Vehículo</label>
                            <input
                                type="text"
                                id="edit-placa"
                                class="parq-input parq-input-placa"
                                value=${editPlaca}
                                onInput=${(e) => setEditPlaca(sanitizePlaca(e.target.value))}
                                required
                            />
                        </div>

                        <div class="mb-3">
                            <label class="parq-label" for="edit-tipo-vehiculo">Categoría / Tipo de Vehículo</label>
                            <select
                                id="edit-tipo-vehiculo"
                                class="parq-select"
                                value=${editTipoId}
                                onChange=${(e) => setEditTipoId(e.target.value)}
                                required
                            >
                                ${tipos.map(
                                    (tv) => html`
                                        <option key=${tv.id} value=${tv.id}>
                                            ${tv.nombre} (${formatMoney(tv.tarifa_hora)}/h)
                                        </option>
                                    `
                                )}
                            </select>
                        </div>

                        <div class="row g-2 mb-3">
                            <div class="col-sm-6">
                                <label class="parq-label" for="edit-estado">Estado del Ticket</label>
                                <select
                                    id="edit-estado"
                                    class="parq-select"
                                    value=${editEstado}
                                    onChange=${(e) => setEditEstado(e.target.value)}
                                    required
                                >
                                    <option value="ACTIVO">ACTIVO</option>
                                    <option value="FINALIZADO">FINALIZADO</option>
                                </select>
                            </div>
                            <div class="col-sm-6">
                                <label class="parq-label" for="edit-precio-final">Precio Final ($)</label>
                                <input
                                    type="number"
                                    id="edit-precio-final"
                                    class="parq-input"
                                    min="0"
                                    step="50"
                                    value=${editPrecioFinal}
                                    onInput=${(e) => setEditPrecioFinal(e.target.value)}
                                />
                            </div>
                        </div>

                        <div>
                            <label class="parq-label" for="edit-motivo">
                                Motivo de la edición administrativa (Obligatorio)
                            </label>
                            <input
                                type="text"
                                id="edit-motivo"
                                class="parq-input"
                                placeholder="Ej. Corrección de placa digitada o categoría errónea"
                                value=${editMotivo}
                                onInput=${(e) => setEditMotivo(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    <div class="parq-modal-footer">
                        <button
                            type="button"
                            class="btn-parq btn-parq-outline"
                            disabled=${savingEdicion}
                            onClick=${() => setTicketEdicion(null)}
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            id="btn-editar-ticket-submit"
                            class="btn-parq btn-parq-amber"
                            disabled=${savingEdicion}
                        >
                            ${savingEdicion ? 'Guardando...' : '⚠️ Confirmar Edición Auditada'}
                        </button>
                    </div>
                </form>
            </${Modal}>

            <!-- Modal 3 (Solo Admin): Eliminar Ticket escribiendo "ELIMINAR" -->
            <${Modal}
                id="modalEliminarTicket"
                variant="danger-red"
                isOpen=${Boolean(ticketEliminar)}
                onClose=${() => !savingEliminar && setTicketEliminar(null)}
                title=${html`🛑 Advertencia Crítica — Eliminar Registro${' '}
                    <span id="del-ticket-placa" class="parq-placa-cell">${ticketEliminar?.placa || ''}</span>`}
            >
                <form id="form-eliminar-ticket" onSubmit=${handleSubmitEliminar}>
                    <div class="parq-modal-body">
                        <div class="parq-alert-banner alert-red">
                            <span class="parq-alert-icon" aria-hidden="true">🚨</span>
                            <div>
                                <strong>Acción Crítica de Borrado Lógico:</strong> Este ticket será retirado del
                                historial operativo y contable. Su usuario, fecha y el estado previo quedarán
                                registrados en <strong>Auditoría</strong>.
                            </div>
                        </div>

                        <div class="mb-3 small" style="color: var(--text-secondary);">
                            ID Ticket: <code id="del-ticket-id">${ticketEliminar?.id || ''}</code> — Ingreso:${' '}
                            <strong id="del-ticket-ingreso">
                                ${formatDateTime(ticketEliminar?.fecha_ingreso)}
                            </strong>
                        </div>

                        <div>
                            <label class="parq-label" for="del-confirm-input">
                                Para confirmar el borrado, escriba exactamente <strong>ELIMINAR</strong>:
                            </label>
                            <input
                                type="text"
                                id="del-confirm-input"
                                class="parq-input parq-confirm-word-input"
                                placeholder="Escriba ELIMINAR"
                                autocomplete="off"
                                value=${delConfirmWord}
                                onInput=${(e) => setDelConfirmWord(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    <div class="parq-modal-footer">
                        <button
                            type="button"
                            class="btn-parq btn-parq-outline"
                            disabled=${savingEliminar}
                            onClick=${() => setTicketEliminar(null)}
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            id="btn-confirmar-eliminar"
                            class="btn-parq btn-parq-danger"
                            disabled=${savingEliminar || delConfirmWord.trim().toUpperCase() !== 'ELIMINAR'}
                        >
                            ${savingEliminar ? 'Eliminando...' : '🗑️ Eliminar Registro Definitivamente'}
                        </button>
                    </div>
                </form>
            </${Modal}>
        </div>
    `;
}
