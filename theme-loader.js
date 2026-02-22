/**
 * Theme Loader — loads theme JSON files from themes/ directory,
 * caches in memory, and dispatches 'theme-changed' events.
 */
(function () {
    'use strict';

    const THEME_STORAGE_KEY = 'appTheme';
    const DEFAULT_THEME = 'midnight_blue';

    // All available theme file basenames (without .json)
    const ALL_THEMES = [
        'autumn', 'blueprint', 'classic_dark', 'classic_light',
        'contrast_zones', 'copper_patina',
        'emerald', 'forest', 'gradient_roads', 'japanese_ink',
        'midnight_blue', 'monochrome_blue', 'neon_cyberpunk', 'noir',
        'ocean', 'pastel_dream', 'sunset', 'terracotta', 'warm_beige'
    ];

    const cache = {};       // name → parsed JSON
    let activeThemeName = null;
    let activeThemeData = null;

    /**
     * Fetch and cache a theme by basename.
     * @param {string} name  e.g. 'midnight_blue'
     * @returns {Promise<object>}
     */
    async function loadTheme(name) {
        if (cache[name]) return cache[name];
        const resp = await fetch(`themes/${name}.json`);
        if (!resp.ok) throw new Error(`Theme "${name}" not found (HTTP ${resp.status})`);
        const data = await resp.json();
        cache[name] = data;
        return data;
    }

    /** Preload all themes (fire-and-forget, useful on idle). */
    function preloadAll() {
        ALL_THEMES.forEach(n => loadTheme(n).catch(() => { }));
    }

    /** Return list of all theme basenames. */
    function getAllThemeNames() {
        return ALL_THEMES.slice();
    }

    /**
     * Determine if a theme is "dark" based on its bg luminance.
     * @param {object} themeData  parsed theme JSON
     * @returns {boolean}
     */
    function isThemeDark(themeData) {
        if (!themeData || !themeData.bg) return true;
        return relativeLuminance(themeData.bg) < 0.35;
    }

    /** Relative luminance of a hex color (sRGB). */
    function relativeLuminance(hex) {
        const r = parseInt(hex.slice(1, 3), 16) / 255;
        const g = parseInt(hex.slice(3, 5), 16) / 255;
        const b = parseInt(hex.slice(5, 7), 16) / 255;
        const toLinear = c => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
    }

    /** Human-readable label from filename: 'midnight_blue' → 'Midnight Blue'. */
    function themeLabel(name) {
        return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    /** Get the currently active theme name. */
    function getActiveThemeName() {
        return activeThemeName;
    }

    /** Get the currently active theme data (may be null until first load). */
    function getActiveThemeData() {
        return activeThemeData;
    }

    /**
     * Set and apply a new theme. Fetches JSON, updates state, dispatches event.
     * @param {string} name  theme basename
     * @returns {Promise<object>}  the theme data
     */
    async function setActiveTheme(name) {
        const data = await loadTheme(name);
        activeThemeName = name;
        activeThemeData = data;
        try { localStorage.setItem(THEME_STORAGE_KEY, name); } catch (e) { }
        document.dispatchEvent(new CustomEvent('theme-changed', { detail: { name, data } }));
        return data;
    }

    /**
     * Initialise: read saved preference, load that theme, dispatch.
     * Call this once on page load.
     * @returns {Promise<object>}
     */
    async function init() {
        let saved = DEFAULT_THEME;
        try {
            const s = localStorage.getItem(THEME_STORAGE_KEY);
            // Migrate old 'dark'/'light' values
            if (s === 'dark') saved = 'midnight_blue';
            else if (s === 'light') saved = 'forest';
            else if (s && ALL_THEMES.includes(s)) saved = s;
        } catch (e) { }
        return setActiveTheme(saved);
    }

    // Expose on window
    window.themeLoader = {
        init,
        loadTheme,
        preloadAll,
        getAllThemeNames,
        isThemeDark,
        themeLabel,
        getActiveThemeName,
        getActiveThemeData,
        setActiveTheme
    };
})();
