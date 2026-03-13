// ./data/hourly_grid_updater.js

/**
 * Обновляет почасовую сетку для первого элемента (Россия)
 * @param {object} macroregionData - данные макрорегиона (первый элемент массива apiData)
 * @param {string} gridId - id контейнера сетки
 */
export function updateHourlyGrid(macroregionData, gridId) {
    if (!macroregionData || !macroregionData.hourly_incidents) return;

    const total = macroregionData.total_incidents || 0;
    const hourlyIncidents = macroregionData.hourly_incidents;
    const grid = document.getElementById(gridId);
    if (!grid) return;

    // Процент от среднего значения за период
    const counts = Object.values(hourlyIncidents);
    const avg = counts.reduce((a,b) => a+b, 0) / counts.length;

    for (let i = 0; i < 24; i++) {
        const span = document.getElementById(`hours-${i}`);
        if (!span) continue;

        const count = hourlyIncidents[i] || 0;

        span.classList.remove('empty', 'low', 'medium', 'high', 'critical');

        if (count === 0 || total === 0) {
            span.textContent = '0';
            span.classList.add('empty');
        } else {
            let percent = (count / total) * 100;
            percent = percent % 1 === 0 ? percent.toFixed(0) : percent.toFixed(1);
            span.textContent = `${count} (${percent}%)`;

            // Уровни нагрузки относительно среднего
            const ratio = count / avg;
            if (ratio < 0.5) span.classList.add('low');
            else if (ratio < 1) span.classList.add('medium');
            else if (ratio < 1.5) span.classList.add('high');
            else span.classList.add('critical');
        }
    }
}