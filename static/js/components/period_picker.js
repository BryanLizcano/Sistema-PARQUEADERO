// Selector interactivo de periodos en Preact (casilla única para Días/Semanas, Mes+Año y Año único)
import { useEffect, useRef, useState } from '../../vendor/hooks.mjs';
import { html } from '../../vendor/htm-preact.mjs';

const MONTH_NAMES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

const MONTH_SHORT = [
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
];

export function pad2(n) {
    return String(n).padStart(2, '0');
}

export function getLocalTodayISO(now = new Date()) {
    return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

export function parseLocalDate(isoStr) {
    if (!isoStr || typeof isoStr !== 'string') return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoStr.trim());
    if (!match) return null;
    const y = Number(match[1]);
    const m = Number(match[2]);
    const d = Number(match[3]);
    // Mediodía local evita desplazamientos por UTC o cambios de horario.
    const date = new Date(y, m - 1, d, 12, 0, 0, 0);
    if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) {
        return null;
    }
    return date;
}

export function formatLocalDate(date) {
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function formatDisplayDate(isoStr) {
    const d = parseLocalDate(isoStr);
    if (!d) return '—';
    return `${pad2(d.getDate())} ${MONTH_SHORT[d.getMonth()]} ${d.getFullYear()}`;
}

export function addDaysISO(isoStr, deltaDays) {
    const d = parseLocalDate(isoStr);
    if (!d) return isoStr;
    d.setDate(d.getDate() + deltaDays);
    return formatLocalDate(d);
}

export function diffDaysInclusive(desdeISO, hastaISO) {
    const a = parseLocalDate(desdeISO);
    const b = parseLocalDate(hastaISO);
    if (!a || !b) return 0;
    return Math.round((b.getTime() - a.getTime()) / 86400000) + 1;
}

export function getDaysInMonth(year, month1to12) {
    return new Date(year, month1to12, 0).getDate();
}

// Calcula lunes y domingo de la semana a la que pertenece una fecha ISO
export function getWeekBoundsMonday(isoStr) {
    const d = parseLocalDate(isoStr);
    if (!d) return null;
    const jsDay = d.getDay(); // 0=Dom, 1=Lun .. 6=Sab
    const offsetToMonday = jsDay === 0 ? -6 : 1 - jsDay;
    const monday = new Date(d.getFullYear(), d.getMonth(), d.getDate() + offsetToMonday, 12, 0, 0, 0);
    const sunday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6, 12, 0, 0, 0);
    return {
        start: formatLocalDate(monday),
        end: formatLocalDate(sunday),
    };
}

// Construye filas de 7 días (Lun..Dom) para el calendario mensual
export function buildCalendarWeeks(viewYear, viewMonth0) {
    const firstOfMonth = new Date(viewYear, viewMonth0, 1, 12, 0, 0, 0);
    const firstJsDay = firstOfMonth.getDay();
    const leadDays = firstJsDay === 0 ? 6 : firstJsDay - 1;

    const lastOfMonth = new Date(viewYear, viewMonth0 + 1, 0, 12, 0, 0, 0);
    const totalMonthDays = lastOfMonth.getDate();
    const totalCells = Math.ceil((leadDays + totalMonthDays) / 7) * 7;

    const weeks = [];
    for (let cellIdx = 0; cellIdx < totalCells; cellIdx += 7) {
        const weekIndex = weeks.length;
        const days = [];
        for (let col = 0; col < 7; col += 1) {
            const dayOffset = cellIdx + col - leadDays;
            const dt = new Date(viewYear, viewMonth0, 1 + dayOffset, 12, 0, 0, 0);
            days.push({
                iso: formatLocalDate(dt),
                dayNum: dt.getDate(),
                inMonth: dt.getMonth() === viewMonth0,
            });
        }
        weeks.push({ weekIndex, days });
    }
    return weeks;
}

export function PeriodPicker({
    tipo,
    desde,
    hasta,
    availableYears = [],
    onRangeChange,
}) {
    const todayISO = getLocalTodayISO();
    const todayDate = parseLocalDate(todayISO);
    const currentYear = todayDate.getFullYear();

    const [isOpen, setIsOpen] = useState(false);
    const [pickingEnd, setPickingEnd] = useState(false);
    const [draftStart, setDraftStart] = useState(null);
    const [hoverISO, setHoverISO] = useState(null);
    const [hintWarning, setHintWarning] = useState('');
    const [viewYear, setViewYear] = useState(currentYear);
    const [viewMonth0, setViewMonth0] = useState(todayDate.getMonth());

    const [selectedMes, setSelectedMes] = useState(todayDate.getMonth() + 1);
    const [selectedMesAnio, setSelectedMesAnio] = useState(currentYear);
    const [selectedAnio, setSelectedAnio] = useState('');

    const wrapRef = useRef(null);
    const closeTimerRef = useRef(null);

    const normalizedYears = [...new Set(
        (availableYears || []).map(Number).filter((y) => Number.isInteger(y) && y > 1900)
    )].sort((a, b) => b - a);

    const monthYearsList = [...new Set([
        currentYear + 1,
        currentYear,
        currentYear - 1,
        ...normalizedYears,
    ])].sort((a, b) => b - a);

    // Sincronizar Año disponible cuando cambian registros o se cambia de modo
    useEffect(() => {
        if (tipo !== 'anio') return;
        if (!normalizedYears.length) {
            if (selectedAnio !== '') setSelectedAnio('');
            if (desde !== '' || hasta !== '') {
                onRangeChange({ desde: '', hasta: '' });
            }
            return;
        }
        const chosen = normalizedYears.includes(Number(selectedAnio))
            ? Number(selectedAnio)
            : normalizedYears[0];
        if (String(chosen) !== String(selectedAnio)) {
            setSelectedAnio(String(chosen));
        }
        const nextDesde = `${chosen}-01-01`;
        const nextHasta = `${chosen}-12-31`;
        if (desde !== nextDesde || hasta !== nextHasta) {
            onRangeChange({ desde: nextDesde, hasta: nextHasta });
        }
    }, [tipo, availableYears]);

    // Reiniciar borrador si cambia el tipo de periodo externo
    useEffect(() => {
        setIsOpen(false);
        setPickingEnd(false);
        setDraftStart(null);
        setHoverISO(null);
        setHintWarning('');

        if (tipo === 'mes') {
            const lastDay = getDaysInMonth(selectedMesAnio, selectedMes);
            onRangeChange({
                desde: `${selectedMesAnio}-${pad2(selectedMes)}-01`,
                hasta: `${selectedMesAnio}-${pad2(selectedMes)}-${pad2(lastDay)}`,
            });
        }
    }, [tipo]);

    const closePopover = (keepDraftFallback = true) => {
        if (closeTimerRef.current) {
            window.clearTimeout(closeTimerRef.current);
            closeTimerRef.current = null;
        }
        if (keepDraftFallback && pickingEnd && draftStart && tipo === 'dias') {
            onRangeChange({ desde: draftStart, hasta: draftStart });
        }
        setPickingEnd(false);
        setDraftStart(null);
        setHoverISO(null);
        setHintWarning('');
        setIsOpen(false);
    };

    useEffect(() => {
        if (!isOpen) return undefined;

        const onOutsideClick = (e) => {
            if (wrapRef.current && !wrapRef.current.contains(e.target)) {
                closePopover(true);
            }
        };
        const onEscape = (e) => {
            if (e.key === 'Escape') {
                closePopover(true);
            }
        };

        document.addEventListener('mousedown', onOutsideClick);
        document.addEventListener('keydown', onEscape);
        return () => {
            document.removeEventListener('mousedown', onOutsideClick);
            document.removeEventListener('keydown', onEscape);
        };
    }, [isOpen, pickingEnd, draftStart, tipo]);

    const openPopover = () => {
        const focus = parseLocalDate(pickingEnd && draftStart ? draftStart : desde) || todayDate;
        setViewYear(focus.getFullYear());
        setViewMonth0(focus.getMonth());
        setHintWarning('');
        setIsOpen(true);
    };

    const stepMonth = (delta) => {
        const next = new Date(viewYear, viewMonth0 + delta, 1, 12, 0, 0, 0);
        setViewYear(next.getFullYear());
        setViewMonth0(next.getMonth());
    };

    const jumpToToday = () => {
        setViewYear(todayDate.getFullYear());
        setViewMonth0(todayDate.getMonth());
        if (tipo === 'dias') {
            setPickingEnd(false);
            setDraftStart(null);
            setHoverISO(null);
            onRangeChange({ desde: todayISO, hasta: todayISO });
        } else if (tipo === 'semanas') {
            const wk = getWeekBoundsMonday(todayISO);
            if (wk) {
                setPickingEnd(true);
                setDraftStart(wk.start);
                onRangeChange({ desde: wk.start, hasta: wk.end });
            }
        }
    };

    const handleDayClick = (clickedISO) => {
        setHintWarning('');

        if (tipo === 'dias') {
            if (!pickingEnd || !draftStart || clickedISO < draftStart) {
                setPickingEnd(true);
                setDraftStart(clickedISO);
                setHoverISO(clickedISO);
                return;
            }

            const maxAllowed = addDaysISO(draftStart, 19);
            if (clickedISO > maxAllowed) {
                setHintWarning('⚠️ Máximo 20 días desde el inicio. Elige un día dentro de la estela.');
                return;
            }

            const finalDesde = draftStart;
            onRangeChange({ desde: finalDesde, hasta: clickedISO });
            setPickingEnd(false);
            setDraftStart(null);
            setHoverISO(null);
            closeTimerRef.current = window.setTimeout(() => closePopover(false), 120);
            return;
        }

        if (tipo === 'semanas') {
            const clickedWeek = getWeekBoundsMonday(clickedISO);
            if (!clickedWeek) return;

            if (!pickingEnd || !draftStart || clickedWeek.start < draftStart) {
                // Clic en cualquier día selecciona toda su semana Lun–Dom
                onRangeChange({ desde: clickedWeek.start, hasta: clickedWeek.end });
                setPickingEnd(true);
                setDraftStart(clickedWeek.start);
                setHoverISO(clickedISO);
                return;
            }

            if (clickedWeek.start === draftStart) {
                onRangeChange({ desde: clickedWeek.start, hasta: clickedWeek.end });
                closePopover(false);
                return;
            }

            const maxWeekEnd = addDaysISO(draftStart, 69);
            if (clickedWeek.end > maxWeekEnd) {
                setHintWarning('⚠️ Máximo 10 semanas desde la semana inicial. Elige dentro de la estela.');
                return;
            }

            onRangeChange({ desde: draftStart, hasta: clickedWeek.end });
            closePopover(false);
        }
    };

    // Modo Mes (2 casillas: Mes y Año)
    if (tipo === 'mes') {
        return html`
            <div id="exp-mes-wrap" class="row g-2">
                <div class="col-7">
                    <label class="parq-label" for="exp-mes">Mes</label>
                    <select
                        id="exp-mes"
                        class="parq-select"
                        value=${String(selectedMes)}
                        onChange=${(e) => {
                            const nextMes = Number(e.target.value);
                            setSelectedMes(nextMes);
                            const lastDay = getDaysInMonth(selectedMesAnio, nextMes);
                            onRangeChange({
                                desde: `${selectedMesAnio}-${pad2(nextMes)}-01`,
                                hasta: `${selectedMesAnio}-${pad2(nextMes)}-${pad2(lastDay)}`,
                            });
                        }}
                    >
                        ${MONTH_NAMES.map(
                            (name, idx) => html`<option key=${idx + 1} value=${String(idx + 1)}>${name}</option>`
                        )}
                    </select>
                </div>
                <div class="col-5">
                    <label class="parq-label" for="exp-mes-anio">Año</label>
                    <select
                        id="exp-mes-anio"
                        class="parq-select"
                        value=${String(selectedMesAnio)}
                        onChange=${(e) => {
                            const nextY = Number(e.target.value);
                            setSelectedMesAnio(nextY);
                            const lastDay = getDaysInMonth(nextY, selectedMes);
                            onRangeChange({
                                desde: `${nextY}-${pad2(selectedMes)}-01`,
                                hasta: `${nextY}-${pad2(selectedMes)}-${pad2(lastDay)}`,
                            });
                        }}
                    >
                        ${monthYearsList.map(
                            (y) => html`<option key=${y} value=${String(y)}>${y}</option>`
                        )}
                    </select>
                </div>
            </div>
        `;
    }

    // Modo Año (1 sola casilla con años que tienen registros en BD)
    if (tipo === 'anio') {
        return html`
            <div id="exp-anio-wrap">
                <label class="parq-label" for="exp-anio">Año con Registros</label>
                <select
                    id="exp-anio"
                    class="parq-select"
                    disabled=${!normalizedYears.length}
                    value=${selectedAnio}
                    onChange=${(e) => {
                        const y = Number(e.target.value);
                        setSelectedAnio(e.target.value);
                        onRangeChange({ desde: `${y}-01-01`, hasta: `${y}-12-31` });
                    }}
                >
                    ${normalizedYears.length
                        ? normalizedYears.map((y) => html`<option key=${y} value=${String(y)}>${y}</option>`)
                        : html`<option value="">Sin años con registros disponibles</option>`}
                </select>
            </div>
        `;
    }

    // Modo Días o Semanas: casilla única interactiva con calendario emergente
    const isWeekMode = tipo === 'semanas';
    const maxDays = isWeekMode ? 70 : 20;
    const daysCount = diffDaysInclusive(desde, hasta);

    let triggerText = '';
    let triggerBadge = '';
    let badgeClass = 'parq-badge parq-badge-sage';

    if (!isWeekMode) {
        if (pickingEnd && draftStart) {
            triggerText = `Desde: ${formatDisplayDate(draftStart)} → Elige Hasta...`;
            triggerBadge = '2do clic: Hasta';
            badgeClass = 'parq-badge parq-badge-amber';
        } else {
            triggerText =
                desde === hasta
                    ? formatDisplayDate(desde)
                    : `${formatDisplayDate(desde)} → ${formatDisplayDate(hasta)}`;
            triggerBadge = `${daysCount} ${daysCount === 1 ? 'día' : 'días'}`;
        }
    } else {
        const weeksCount = Math.max(1, Math.round(daysCount / 7));
        triggerText = `${formatDisplayDate(desde)} → ${formatDisplayDate(hasta)}`;
        triggerBadge = `${weeksCount} ${weeksCount === 1 ? 'semana' : 'semanas'}`;
        if (pickingEnd) badgeClass = 'parq-badge parq-badge-amber';
    }

    const defaultHint = isWeekMode
        ? pickingEnd && draftStart
            ? 'Semana inicial marcada. Haz clic en la misma semana para confirmar, o en otra posterior (máx. 10 sem.).'
            : 'Cada fila tiene su color de semana. Clic en cualquier día para elegir toda su semana.'
        : pickingEnd && draftStart
        ? `Paso 2: Escoge Hasta (la sombra marca los ${maxDays} días permitidos desde ${formatDisplayDate(draftStart)}).`
        : 'Paso 1: Haz clic en el día Desde y luego en el día Hasta.';

    const anchorStart = pickingEnd ? draftStart : desde;
    const allowedMaxISO = pickingEnd && draftStart ? addDaysISO(draftStart, maxDays - 1) : null;
    const hoverWeekBounds = isWeekMode && hoverISO ? getWeekBoundsMonday(hoverISO) : null;
    const weeks = buildCalendarWeeks(viewYear, viewMonth0);

    return html`
        <div id="exp-single-picker-wrap" class="parq-period-picker" ref=${wrapRef}>
            <label class="parq-label" id="exp-single-label" for="btn-period-trigger">
                ${isWeekMode ? 'Semana(s) del Calendario' : 'Rango de Días (Desde → Hasta)'}
            </label>
            <button
                type="button"
                id="btn-period-trigger"
                class="parq-period-trigger"
                aria-expanded=${isOpen ? 'true' : 'false'}
                aria-controls="exp-calendar-popover"
                onClick=${() => (isOpen ? closePopover(true) : openPopover())}
            >
                <span class="parq-period-trigger-value" id="period-trigger-text">${triggerText}</span>
                <span class=${badgeClass} id="period-trigger-badge">${triggerBadge}</span>
            </button>

            <div
                class=${`parq-cal-popover ${isOpen ? 'is-open' : ''}`}
                id="exp-calendar-popover"
                role="dialog"
                aria-label="Selector de periodo"
                aria-hidden=${isOpen ? 'false' : 'true'}
            >
                <div class="parq-cal-header">
                    <button
                        type="button"
                        class="parq-cal-nav-btn"
                        id="btn-cal-prev"
                        aria-label="Mes anterior"
                        onClick=${() => stepMonth(-1)}
                    >
                        ‹
                    </button>
                    <strong class="parq-cal-title" id="cal-month-title">
                        ${MONTH_NAMES[viewMonth0]} ${viewYear}
                    </strong>
                    <button
                        type="button"
                        class="parq-cal-nav-btn"
                        id="btn-cal-next"
                        aria-label="Mes siguiente"
                        onClick=${() => stepMonth(1)}
                    >
                        ›
                    </button>
                </div>

                <div class="parq-cal-hint" id="cal-hint-bar">${hintWarning || defaultHint}</div>

                <div
                    class=${`parq-cal-weekdays ${isWeekMode ? 'is-week-mode' : ''}`}
                    id="cal-weekdays"
                >
                    ${isWeekMode ? html`<span>Sem</span>` : null}
                    <span>Lun</span><span>Mar</span><span>Mié</span><span>Jue</span>
                    <span>Vie</span><span>Sáb</span><span>Dom</span>
                </div>

                <div
                    class="parq-cal-grid"
                    id="cal-grid-body"
                    onMouseLeave=${() => setHoverISO(null)}
                >
                    ${weeks.map(({ weekIndex, days }) => {
                        const isHoveredRow =
                            isWeekMode &&
                            hoverWeekBounds &&
                            days.some((d) => d.iso >= hoverWeekBounds.start && d.iso <= hoverWeekBounds.end);

                        const rowClass = [
                            'parq-cal-week',
                            isWeekMode ? `is-week-mode week-color-${weekIndex % 6}` : '',
                            isHoveredRow ? 'is-week-row-hover' : '',
                        ]
                            .filter(Boolean)
                            .join(' ');

                        return html`
                            <div key=${weekIndex} class=${rowClass}>
                                ${isWeekMode
                                    ? html`<span
                                          class=${`parq-cal-week-tag week-tag-${weekIndex % 6}`}
                                          title=${`Semana ${weekIndex + 1} del calendario`}
                                      >
                                          S${weekIndex + 1}
                                      </span>`
                                    : null}

                                ${days.map((cell) => {
                                    const classes = ['parq-cal-day'];
                                    let titleText = '';

                                    if (!cell.inMonth) classes.push('is-outside-month');
                                    if (cell.iso === todayISO) classes.push('is-today');

                                    if (pickingEnd && draftStart) {
                                        if (cell.iso === draftStart) {
                                            classes.push('is-range-start', 'is-picking');
                                        } else if (allowedMaxISO && cell.iso > draftStart && cell.iso <= allowedMaxISO) {
                                            classes.push('is-allowed-trail');
                                            if (cell.iso === allowedMaxISO) classes.push('is-allowed-limit-end');
                                            if (
                                                hoverISO &&
                                                hoverISO >= draftStart &&
                                                hoverISO <= allowedMaxISO &&
                                                cell.iso <= hoverISO
                                            ) {
                                                classes.push('is-hover-trail');
                                            }
                                        } else if (allowedMaxISO && cell.iso > allowedMaxISO) {
                                            classes.push('is-out-of-limit');
                                            titleText = isWeekMode
                                                ? 'Excede el límite máximo de 10 semanas'
                                                : 'Excede el límite máximo de 20 días';
                                        }

                                        if (
                                            isWeekMode &&
                                            desde &&
                                            hasta &&
                                            cell.iso >= desde &&
                                            cell.iso <= hasta
                                        ) {
                                            if (cell.iso === desde) classes.push('is-range-start');
                                            else if (cell.iso === hasta) classes.push('is-range-end');
                                            else classes.push('is-in-range');
                                        }
                                    } else if (anchorStart && hasta) {
                                        if (cell.iso === anchorStart && cell.iso === hasta) {
                                            classes.push('is-range-start', 'is-range-end');
                                        } else if (cell.iso === anchorStart) {
                                            classes.push('is-range-start');
                                        } else if (cell.iso === hasta) {
                                            classes.push('is-range-end');
                                        } else if (cell.iso > anchorStart && cell.iso < hasta) {
                                            classes.push('is-in-range');
                                        }
                                    }

                                    return html`
                                        <button
                                            key=${cell.iso}
                                            type="button"
                                            class=${classes.join(' ')}
                                            title=${titleText}
                                            onMouseEnter=${() => setHoverISO(cell.iso)}
                                            onClick=${() => handleDayClick(cell.iso)}
                                        >
                                            ${cell.dayNum}
                                        </button>
                                    `;
                                })}
                            </div>
                        `;
                    })}
                </div>

                <div class="parq-cal-footer">
                    <span class="small" style="color: var(--text-muted);" id="cal-footer-note">
                        ${isWeekMode
                            ? 'Selección semanal completa Lun–Dom (máx. 10 sem.)'
                            : 'Estela = rango permitido (máx. 20 días)'}
                    </span>
                    <div class="d-flex gap-2">
                        <button
                            type="button"
                            class="btn-parq btn-parq-outline btn-parq-sm"
                            id="btn-cal-today"
                            onClick=${jumpToToday}
                        >
                            Hoy
                        </button>
                        ${isWeekMode && desde && hasta
                            ? html`
                                  <button
                                      type="button"
                                      class="btn-parq btn-parq-sage btn-parq-sm"
                                      id="btn-cal-done"
                                      onClick=${() => closePopover(false)}
                                  >
                                      ✓ Usar esta semana
                                  </button>
                              `
                            : null}
                    </div>
                </div>
            </div>
        </div>
    `;
}
