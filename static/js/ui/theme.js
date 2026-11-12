const THEME_KEY = 'parq_theme';

export function getStoredTheme() {
    try {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored === 'dark' || stored === 'light') {
            return stored;
        }
    } catch (_) {
        // Ignorar bloqueos de localStorage en modo quiosco
    }
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
}

export function applyTheme(theme) {
    const normalized = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', normalized);
    try {
        localStorage.setItem(THEME_KEY, normalized);
    } catch (_) {}
    return normalized;
}

export function initTheme() {
    return applyTheme(getStoredTheme());
}

export function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || getStoredTheme();
    return applyTheme(current === 'dark' ? 'light' : 'dark');
}
