export function getCssVar(varName, fallback = '') {
    const value = getComputedStyle(document.documentElement)
        .getPropertyValue(`--${varName}`)
        .trim();

    return value || fallback;
}

export function remToPx(rem) {
    if (!rem) return 0;

    const remValue = parseFloat(rem);
    const rootFontSize = parseFloat(
        getComputedStyle(document.documentElement).fontSize
    );

    return Math.round(remValue * rootFontSize);
}

export function getChartColors() {
    return {
        blue: getCssVar('blue-color', '#5a7fff'),
        magenta: getCssVar('magenta-color', '#b23ae8'),
        green: getCssVar('green-color', '#36b37e'),
        yellow: getCssVar('yellow-color', '#bb9f4e'),
        red: getCssVar('red-color', '#d93f3f'),
        cyan: getCssVar('cyan-color', '#17a2b8'),
        gray: getCssVar('gray-color', '#949497'),

        pink: getCssVar('pink-color', '#e255a1;'),
        brown: getCssVar('brown-color', '#8d6e63'),
        orange: getCssVar('orange-color', '#f2994a'),
        purple: getCssVar('purple-color', '#6f5bd7'),
        teal: getCssVar('teal-color', '#2f9e9e'),

        color: getCssVar('color', '#1b1b1f'),
        add_color: getCssVar('add-color', '#2e2e33'),
        extra: getCssVar('extra-color', 'rgba(27, 27, 31, 0.2)'),

        bg: getCssVar('background-color', 'rgb(244, 245, 247)'),
        add_bg: getCssVar('add-background-color', 'rgb(225, 228, 235)'),
    };
}
export function getChartFonts() {
    return {
        xxs: remToPx(getCssVar('font-xxs', '0.625rem')),
        xs: remToPx(getCssVar('font-xs', '0.75rem')),
        sm: remToPx(getCssVar('font-sm', '0.875rem')),
        md: remToPx(getCssVar('font-md', '1rem')),
        lg: remToPx(getCssVar('font-lg', '1.25rem')),
        xl: remToPx(getCssVar('font-xl', '1.5rem')),
    };
}

export function getChartRadius() {
    return {
        xxs: getCssVar('radius-xxs', '1px'),
        xs: getCssVar('radius-xs', '2px'),
        sm: getCssVar('radius-sm', '4px'),
        md: getCssVar('radius-md', '8px'),
        lg: getCssVar('radius-lg', '12px'),
        xl: getCssVar('radius-xl', '20px'),
    };
}

export function observeThemeChange(callback) {
    const observer = new MutationObserver(() => callback());

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
    });
}