/**
 * Преобразует API ответ в формат Chart.js
 */
export function adaptDailyIncidents(apiData) {
    if (!Array.isArray(apiData)) {
        return { labels: [], datasets: [] };
    }

    // 1. Собираем все даты
    const dateSet = new Set();

    apiData.forEach(region => {
        Object.keys(region.daily_incidents || {}).forEach(date => {
            dateSet.add(date);
        });
    });

    // 2. Сортируем даты
    const labels = Array.from(dateSet).sort(
        (a, b) => new Date(a) - new Date(b)
    );

    // 3. Формируем datasets
    const datasets = apiData.map(region => ({
        label: region.macroregion,
        data: labels.map(
            date => region.daily_incidents?.[date] ?? 0
        ),
        fill: false
    }));

    return { labels, datasets };
}
