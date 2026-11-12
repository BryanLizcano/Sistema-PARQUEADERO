import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../..');

// Simulación mínima de entorno navegador para importar los módulos ES de la SPA
globalThis.window = {
    location: { pathname: '/registros.html', href: '' },
    history: {
        pushState: () => {},
        replaceState: () => {},
    },
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
    addEventListener: () => {},
    removeEventListener: () => {},
    matchMedia: () => ({ matches: false }),
};
globalThis.document = {
    title: '',
    body: { classList: { toggle: () => {} } },
    addEventListener: () => {},
    removeEventListener: () => {},
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    documentElement: { setAttribute: () => {}, getAttribute: () => 'light' },
};

const {
    debounce,
    validateExportRange,
    PAGE_LIMIT,
    registros,
    registrosLoaded,
    registrosTotal,
    kpiStats,
    prependTicketInStore,
    updateTicketInStore,
    removeTicketFromStore,
    resetRegistrosStore,
} = await import('./store/registros_store.js');

const {
    currentUser,
    isAdmin,
    currentRoute,
    pathToRoute,
    routeToPath,
    handleUnauthorized,
    upsertTipoInStore,
    tiposVehiculo,
    activeTicketPreview,
    openTicketPreview,
    closeTicketPreview,
} = await import('./store/app_store.js');

const {
    getLocalTodayISO,
    getWeekBoundsMonday,
    buildCalendarWeeks,
    getDaysInMonth,
} = await import('./components/period_picker.js');

const { render } = await import('../vendor/preact.mjs');
const { html } = await import('../vendor/htm-preact.mjs');

test('Preact + htm + Signals vendored ESM generan VNodes válidos sin CDN ni build step', () => {
    assert.equal(typeof render, 'function');
    const vnode = html`<div class="ok">SPA Lista</div>`;
    assert.equal(vnode.type, 'div');
    assert.equal(vnode.props.class, 'ok');
});

test('debounce agrupa llamadas rápidas y ejecuta una sola vez (< 300ms)', async () => {
    let count = 0;
    let lastArg = null;
    const fn = debounce((val) => {
        count += 1;
        lastArg = val;
    }, 60);

    fn('A');
    fn('AB');
    fn('ABC');
    assert.equal(count, 0);

    await new Promise((resolve) => setTimeout(resolve, 110));
    assert.equal(count, 1);
    assert.equal(lastArg, 'ABC');
});

test('validateExportRange valida límites visuales de días (<=20), semanas (<=10), mes (<=31) y año (<=366)', () => {
    assert.equal(validateExportRange('dias', '2026-11-01', '2026-11-20').valid, true);
    const badDias = validateExportRange('dias', '2026-11-01', '2026-11-21');
    assert.equal(badDias.valid, false);
    assert.equal(badDias.days, 21);

    assert.equal(validateExportRange('semanas', '2026-09-01', '2026-11-09').valid, true);
    assert.equal(validateExportRange('semanas', '2026-09-01', '2026-11-10').valid, false);

    assert.equal(validateExportRange('mes', '2026-10-01', '2026-10-31').valid, true);
    assert.equal(validateExportRange('mes', '2026-10-01', '2026-11-01').valid, false);

    assert.equal(validateExportRange('anio', '2026-01-01', '2026-12-31').valid, true);
    assert.equal(validateExportRange('anio', '2026-01-01', '2027-01-03').valid, false);
    assert.equal(validateExportRange('anio', '', '').valid, false);
});

test('period_picker calcula fecha local, semana completa Lun-Dom, días del mes y cuadrícula mensual', () => {
    const fakeNight = new Date(2026, 10, 11, 21, 30, 0);
    assert.equal(getLocalTodayISO(fakeNight), '2026-11-11');

    assert.deepEqual(getWeekBoundsMonday('2026-11-11'), {
        start: '2026-11-09',
        end: '2026-11-15',
    });
    assert.deepEqual(getWeekBoundsMonday('2026-11-15'), {
        start: '2026-11-09',
        end: '2026-11-15',
    });

    assert.equal(getDaysInMonth(2024, 2), 29);
    assert.equal(getDaysInMonth(2026, 2), 28);

    const weeks = buildCalendarWeeks(2026, 10);
    assert.ok(weeks.length >= 5);
    assert.equal(weeks[0].days.length, 7);
});

test('SPA Stores: router, permisos reactivos y mutaciones en sitio actualizan KPIs sin recarga completa', () => {
    assert.equal(pathToRoute('/registros.html'), 'registros');
    assert.equal(pathToRoute('/configuracion.html'), 'configuracion');
    assert.equal(pathToRoute('/login.html'), 'login');
    assert.equal(pathToRoute('/'), 'operacion');
    assert.equal(routeToPath('registros'), 'registros.html');

    currentUser.value = { id: 'u1', nombre: 'Admin', rol: 'admin', activo: true };
    assert.equal(isAdmin.value, true);

    resetRegistrosStore();
    registrosLoaded.value = true;
    registros.value = [
        { id: 't1', placa: 'ABC123', estado: 'ACTIVO', precio_total: null, precio_final: null },
        { id: 't2', placa: 'XYZ999', estado: 'FINALIZADO', fecha_salida: '2026-11-11T10:00:00', precio_total: 4000, precio_final: 4000 },
    ];
    registrosTotal.value = 2;

    assert.deepEqual(kpiStats.value, { activos: 1, finalizados: 1, recaudo: 4000 });

    // Mutar precio in-situ actualiza recaudo sin recargar tabla
    updateTicketInStore({ id: 't2', precio_final: 5500, motivo_ajuste: 'Lavado adicional' });
    assert.deepEqual(kpiStats.value, { activos: 1, finalizados: 1, recaudo: 5500 });

    // Ingreso nuevo desde Operación inserta arriba en caché
    prependTicketInStore({ id: 't3', placa: 'NEW111', estado: 'ACTIVO', precio_total: null });
    assert.equal(registros.value.length, 3);
    assert.equal(registros.value[0].id, 't3');
    assert.equal(registrosTotal.value, 3);
    assert.equal(kpiStats.value.activos, 2);

    // Borrado lógico elimina en sitio sin re-fetch
    removeTicketFromStore('t1');
    assert.equal(registros.value.length, 2);
    assert.equal(registrosTotal.value, 2);

    // Tarifas compartidas reactivamente entre vistas
    tiposVehiculo.value = [{ id: 'tv1', nombre: 'CARRO', tarifa_hora: 2000 }];
    upsertTipoInStore({ id: 'tv1', nombre: 'CARRO', tarifa_hora: 2500 });
    assert.equal(tiposVehiculo.value[0].tarifa_hora, 2500);

    // Vista previa del ticket superpuesta en la misma pestaña
    openTicketPreview({ id: 't99', placa: 'BAH999', fecha_ingreso: '2026-11-11T10:00:00' }, 'ingreso', { autoPrint: false });
    assert.equal(activeTicketPreview.value?.ticket?.placa, 'BAH999');
    assert.equal(activeTicketPreview.value?.tipo, 'ingreso');
    closeTicketPreview();
    assert.equal(activeTicketPreview.value, null);

    // Sesión 401 cambia ruta reactivamente a login y limpia store
    handleUnauthorized();
    assert.equal(currentUser.value, null);
    assert.equal(currentRoute.value, 'login');
    assert.equal(registros.value.length, 0);
});

test('Estructura SPA libre de CDN, roles estrictos, PeriodPicker y código de impresión intacto', () => {
    const htmlFiles = ['index.html', 'login.html', 'registros.html', 'configuracion.html'];
    htmlFiles.forEach((file) => {
        const htmlSrc = fs.readFileSync(path.join(rootDir, 'static', file), 'utf8');
        assert.match(htmlSrc, /id="app"/);
        assert.match(htmlSrc, /src="js\/app\.js"/);
        assert.doesNotMatch(htmlSrc, /cdn\.jsdelivr\.net|bootstrap/i);
    });

    const jsReg = fs.readFileSync(path.join(rootDir, 'static/js/views/registros_view.js'), 'utf8');
    const jsOp = fs.readFileSync(path.join(rootDir, 'static/js/views/operacion_view.js'), 'utf8');
    const jsCfg = fs.readFileSync(path.join(rootDir, 'static/js/views/configuracion_view.js'), 'utf8');
    const jsPicker = fs.readFileSync(path.join(rootDir, 'static/js/components/period_picker.js'), 'utf8');
    const jsModal = fs.readFileSync(path.join(rootDir, 'static/js/components/modal.js'), 'utf8');
    const jsTicketModal = fs.readFileSync(path.join(rootDir, 'static/js/components/ticket_modal.js'), 'utf8');
    const css = fs.readFileSync(path.join(rootDir, 'static/style.css'), 'utf8');
    const ticketHtml = fs.readFileSync(path.join(rootDir, 'static/ticket.html'), 'utf8');

    // El modal solo ejecuta auto-focus al cambiar [isOpen] para no perder el foco al escribir
    assert.match(jsModal, /\},\s*\[isOpen\]\)/);
    assert.doesNotMatch(jsTicketModal, /pos-logo-box/);

    assert.equal(PAGE_LIMIT, 50);
    assert.match(jsReg, /id="paginacion-indicador"/);
    assert.match(jsReg, /\/api\/exportar/);
    assert.match(jsReg, /loadExportYears/);
    assert.match(jsReg, /data-no-transition/);
    assert.match(jsReg, /15000/);

    assert.match(jsPicker, /id="btn-period-trigger"/);
    assert.match(jsPicker, /id="exp-calendar-popover"/);
    assert.match(jsPicker, /id="exp-mes-wrap"/);
    assert.match(jsPicker, /id="exp-anio-wrap"/);
    assert.match(jsPicker, /is-allowed-trail/);

    assert.match(css, /\.week-color-0/);
    assert.match(css, /\.parq-card-overflow-visible/);

    // Modales por rol y confirmación "ELIMINAR"
    assert.match(jsReg, /id="modalEditarTicket"/);
    assert.match(jsReg, /id="modalEliminarTicket"/);
    assert.match(jsReg, /!== 'ELIMINAR'/);
    assert.match(jsCfg, /id="modalConfirmarTarifa"/);
    assert.match(jsCfg, /\$\{admin/);

    // Impresión y reglamento del ticket POS superpuesto en la misma pestaña (PARQUEADERO BAHONDO, objetos personales y tarjeta de propiedad)
    assert.match(ticketHtml, /window\.print\(\)/);
    assert.match(jsTicketModal, /PARQUEADERO BAHONDO/);
    assert.match(jsTicketModal, /objetos personales/i);
    assert.match(jsTicketModal, /TARJETA DE PROPIEDAD/);
    assert.match(jsTicketModal, /id="printable-ticket"/);
    assert.match(jsOp, /openTicketPreview\(data,\s*'ingreso'\)/);
    assert.match(jsOp, /openTicketPreview\(data,\s*'salida'\)/);
    assert.match(jsReg, /openTicketPreview\(ticket,\s*tipoImpresion\)/);
});
