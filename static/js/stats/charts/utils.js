export function remToPx(value) {
    if (!value) return 14;
    if (value.endsWith('rem')) {
        const base = parseFloat(
            getComputedStyle(document.documentElement).fontSize
        );
        return parseFloat(value) * base;
    }
    return parseFloat(value);
}

export function getThemeVars() {
    const styles = getComputedStyle(document.documentElement);
    const getVar = (name) => styles.getPropertyValue(name).trim();

    return {
        // Базовые цвета текста
        textColor: getVar('--color'),
        addTextColor: getVar('--add-color'),
        
        // Служебные цвета для графиков
        gridColor: getVar('--extra-color'),
        titleColor: getVar('--color'),
        
        // Основная палитра
        gray: getVar('--gray-color'),
        red: getVar('--red-color'),
        green: getVar('--green-color'),
        blue: getVar('--blue-color'),
        yellow: getVar('--yellow-color'),
        magenta: getVar('--magenta-color'),
        cyan: getVar('--cyan-color'),

        // Фоны
        backgroundColor: getVar('--background-color'),
        addBackground: getVar('--add-background-color'),

        // Шрифты (конвертируем в числа для Chart.js)
        fontXxs: remToPx(getVar('--font-xxs')),
        fontXs: remToPx(getVar('--font-xs')),
        fontSm: remToPx(getVar('--font-sm')),
        fontMd: remToPx(getVar('--font-md')),

        // Радиусы
        radiusSm: remToPx(getVar('--radius-sm')),
        radiusMd: remToPx(getVar('--radius-md')),
        
        // Совместимость со старым кодом, если где-то используется напрямую
        color: getVar('--color'),
        add_color: getVar('--add-color'),
        extra_color: getVar('--extra-color')
    };
}

export function getCssVar(name, fallback = '#999') {
    return (
        getComputedStyle(document.documentElement)
            .getPropertyValue(name)
            .trim() || fallback
    );
}
