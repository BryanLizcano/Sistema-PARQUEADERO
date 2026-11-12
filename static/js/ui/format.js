// Utilidades compartidas de formato para la interfaz SPA

export function formatMoney(value) {
    const num = Number(value ?? 0);
    if (Number.isNaN(num)) return '$0';
    return `$${num.toLocaleString()}`;
}

export function formatNullableMoney(value) {
    if (value === null || value === undefined || value === '') return '—';
    const num = Number(value);
    if (Number.isNaN(num)) return '—';
    return `$${num.toLocaleString()}`;
}

export function formatDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleString();
}

export function sanitizePlaca(value) {
    return String(value || '')
        .toUpperCase()
        .replace(/[^A-Z0-9-]/g, '');
}
