// Modal superpuesto de vista previa e impresión directa de ticket POS en la misma pestaña
import { useEffect } from '../../vendor/hooks.mjs';
import { html } from '../../vendor/htm-preact.mjs';
import { activeTicketPreview, closeTicketPreview } from '../store/app_store.js';

function formatFechaTicket(iso) {
    if (!iso) return '---';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString('es-CO', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

export function TicketPreviewModal() {
    const preview = activeTicketPreview.value;

    useEffect(() => {
        if (!preview) return undefined;

        const onKeyDown = (e) => {
            if (e.key === 'Escape') {
                closeTicketPreview();
            }
        };
        document.addEventListener('keydown', onKeyDown);

        let printTimer = null;
        if (preview.autoPrint && typeof window !== 'undefined' && typeof window.print === 'function') {
            printTimer = window.setTimeout(() => {
                window.print();
            }, 260);
        }

        return () => {
            document.removeEventListener('keydown', onKeyDown);
            if (printTimer) {
                window.clearTimeout(printTimer);
            }
        };
    }, [preview]);

    if (!preview || !preview.ticket) return null;

    const t = preview.ticket;
    const shortId = String(t.id || '').split('-')[0].toUpperCase();
    const esSalida = Boolean((preview.tipo === 'salida' || t.estado === 'FINALIZADO') && t.fecha_salida);
    const montoCobrado = Number(t.precio_final ?? t.precio_total ?? 0);

    return html`
        <div
            class="parq-ticket-overlay"
            id="modalTicketPreview"
            role="dialog"
            aria-modal="true"
            aria-label="Vista previa de impresión del ticket"
            onClick=${(e) => {
                if (e.target === e.currentTarget) {
                    closeTicketPreview();
                }
            }}
        >
            <div class="pos-screen-toolbar no-print">
                <button
                    type="button"
                    id="btn-print-now"
                    class="btn-parq btn-parq-sage btn-parq-sm"
                    onClick=${() => window.print()}
                >
                    🖨️ Imprimir Ticket
                </button>
                <button
                    type="button"
                    id="btn-close-ticket-preview"
                    class="btn-parq btn-parq-outline btn-parq-sm"
                    style="background: #fff; color: #0f172a;"
                    onClick=${closeTicketPreview}
                >
                    ✕ Cerrar Vista Previa (Esc)
                </button>
            </div>

            <div id="printable-ticket" class="pos-ticket">
                <div class="pos-header">
                    <div class="pos-brand-box">
                        <h3 class="pos-brand-title" id="t-nombre-parq">PARQUEADERO BAHONDO</h3>
                    </div>
                    <div class="pos-subtitle" style="font-size: 10px;">CONTROL Y CUSTODIA VEHICULAR</div>
                </div>

                <div class="pos-type-banner" id="t-titulo">
                    ${esSalida ? 'RECIBO DE SALIDA Y PAGO' : 'COMPROBANTE DE INGRESO'}
                </div>

                <div class="pos-placa-box">
                    <div class="pos-placa-label">PLACA DEL VEHÍCULO</div>
                    <div class="pos-placa-value" id="t-placa">${t.placa}</div>
                </div>

                <div class="row-data">
                    <span class="row-label">TICKET N°:</span>
                    <span class="row-val" id="t-id">#${shortId}</span>
                </div>
                <div class="row-data">
                    <span class="row-label">ESTADO:</span>
                    <span class="row-val" id="t-estado">
                        ${esSalida ? 'LIQUIDADO / FINALIZADO' : 'ACTIVO EN PARQUEADERO'}
                    </span>
                </div>
                <div class="row-data">
                    <span class="row-label">INGRESO:</span>
                    <span class="row-val" id="t-ingreso">${formatFechaTicket(t.fecha_ingreso)}</span>
                </div>

                ${esSalida
                    ? html`
                          <div id="seccion-salida">
                              <div class="row-data">
                                  <span class="row-label">SALIDA:</span>
                                  <span class="row-val" id="t-salida">${formatFechaTicket(t.fecha_salida)}</span>
                              </div>
                              <div class="row-data">
                                  <span class="row-label">ESTADÍA:</span>
                                  <span class="row-val">
                                      <span id="t-horas">${t.total_horas ?? 1}</span> hora(s)
                                  </span>
                              </div>
                              ${t.motivo_ajuste
                                  ? html`
                                        <div class="row-data" id="fila-ajuste">
                                            <span class="row-label">AJUSTE:</span>
                                            <span class="row-val" id="t-ajuste" style="font-size: 11px;">
                                                ${t.motivo_ajuste}
                                            </span>
                                        </div>
                                    `
                                  : null}

                              <div class="pos-total-box">
                                  <span>TOTAL A PAGAR:</span>
                                  <span id="t-total">$${montoCobrado.toLocaleString()}</span>
                              </div>
                          </div>
                      `
                    : null}

                <div class="pos-rules-box">
                    <div class="pos-rules-title">REGLAMENTO Y CONDICIONES</div>
                    <ul class="pos-rules-list">
                        <li>
                            <strong>OBJETOS PERSONALES:</strong> No nos hacemos responsables por objetos personales,
                            cascos, paquetes o elementos de valor dejados en el vehículo.
                        </li>
                        <li>
                            <strong>PÉRDIDA DEL TICKET:</strong> En caso de perder este ticket, para retirar el
                            vehículo se debe presentar obligatoriamente la <strong>TARJETA DE PROPIEDAD</strong> y
                            documento de identidad.
                        </li>
                        <li>Verifique que la placa registrada coincida con su vehículo.</li>
                    </ul>
                </div>

                <div class="text-center" style="font-size: 11.5px; font-weight: 700; margin-top: 6px;">
                    <div id="t-mensaje">
                        ${esSalida
                            ? 'Pago registrado exitosamente.'
                            : 'Conserve este ticket para retirar su vehículo.'}
                    </div>
                    <div style="margin-top: 3px; font-weight: 900; letter-spacing: 0.04em;">
                        PARQUEADERO BAHONDO — ¡Gracias por su visita!
                    </div>
                </div>

                <div class="pos-barcode-wrap">
                    <svg width="210" height="32" viewBox="0 0 210 32" aria-hidden="true">
                        <rect x="2" y="0" width="3" height="32" fill="#000" />
                        <rect x="8" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="13" y="0" width="4" height="32" fill="#000" />
                        <rect x="20" y="0" width="2" height="32" fill="#000" />
                        <rect x="25" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="30" y="0" width="5" height="32" fill="#000" />
                        <rect x="38" y="0" width="2" height="32" fill="#000" />
                        <rect x="43" y="0" width="3" height="32" fill="#000" />
                        <rect x="50" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="55" y="0" width="4" height="32" fill="#000" />
                        <rect x="62" y="0" width="2" height="32" fill="#000" />
                        <rect x="68" y="0" width="3" height="32" fill="#000" />
                        <rect x="74" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="79" y="0" width="5" height="32" fill="#000" />
                        <rect x="87" y="0" width="2" height="32" fill="#000" />
                        <rect x="92" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="97" y="0" width="4" height="32" fill="#000" />
                        <rect x="104" y="0" width="3" height="32" fill="#000" />
                        <rect x="110" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="115" y="0" width="4" height="32" fill="#000" />
                        <rect x="122" y="0" width="2" height="32" fill="#000" />
                        <rect x="127" y="0" width="5" height="32" fill="#000" />
                        <rect x="135" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="140" y="0" width="3" height="32" fill="#000" />
                        <rect x="146" y="0" width="2" height="32" fill="#000" />
                        <rect x="151" y="0" width="4" height="32" fill="#000" />
                        <rect x="158" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="163" y="0" width="5" height="32" fill="#000" />
                        <rect x="171" y="0" width="2" height="32" fill="#000" />
                        <rect x="176" y="0" width="3" height="32" fill="#000" />
                        <rect x="182" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="187" y="0" width="4" height="32" fill="#000" />
                        <rect x="194" y="0" width="2" height="32" fill="#000" />
                        <rect x="199" y="0" width="1.5" height="32" fill="#000" />
                        <rect x="204" y="0" width="4" height="32" fill="#000" />
                    </svg>
                    <div class="pos-barcode-code" id="t-barcode-code">*${t.placa}-${shortId}*</div>
                </div>
            </div>
        </div>
    `;
}
