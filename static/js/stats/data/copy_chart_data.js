import { adaptSla } from './sla_adapter.js';

export function chartToTableText(chartOrCharts, firstColumnLabel = 'Показатель') {
    if (!chartOrCharts) return '';

    // SLA — массив графиков
    if (Array.isArray(chartOrCharts)) {
        const headers = ['Категория / Регион'];
        const rowsMap = {}; // ключ — категория, значение — массив по регионам

        chartOrCharts.forEach((chart) => {
            if (!chart?.data?.datasets) return;

            const regionLabel = chart.options?.title?.text ?? 'Регион';
            headers.push(regionLabel);

            chart.data.datasets.forEach(ds => {
                const category = ds.label ?? 'Категория';
                if (!rowsMap[category]) rowsMap[category] = [];
                // берём первое значение в массиве data
                rowsMap[category].push(ds.data?.[0] ?? 0);
            });
        });

        const rows = [headers.join('\t')];
        for (const category of Object.keys(rowsMap)) {
            rows.push([category, ...rowsMap[category]].join('\t'));
        }

        return rows.join('\n');
    }

    // обычный график
    const labels = chartOrCharts.data.labels || [];
    const datasets = chartOrCharts.data.datasets || [];
    const headerLabels = datasets.map(d => d.label ?? 'Series');
    const header = [firstColumnLabel, ...headerLabels].join('\t');
    const rows = [header];

    labels.forEach((label, idx) => {
        const row = [label ?? `Label ${idx + 1}`];
        datasets.forEach(ds => row.push(ds.data?.[idx] ?? 0));
        rows.push(row.join('\t'));
    });

    return rows.join('\n');
}

export function updateCopyButton(chartCardId, chartOrCharts, firstColumnLabel = 'Показатель') {
    const card = document.getElementById(chartCardId);
    if (!card) return;

    const btn = card.querySelector('.copy-chart-data-btn');
    if (!btn) return;

    btn.dataset.text = chartToTableText(chartOrCharts, firstColumnLabel);
}

export function updateSlaCopyData(containerId, apiData, type = 'avr') {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Заголовки регионов
    const regions = apiData.map(item => item.macroregion ?? 'Регион');

    // Категории SLA
    const categories = ['Просрочено', 'Закрыто вовремя', 'Менее часа', 'В работе'];

    // Собираем строки
    const rows = categories.map((cat, idx) => {
        const values = apiData.map(item => adaptSla(item, type)[idx] ?? 0);
        return [cat, ...values].join('\t');
    });

    // Формируем текст для копирования
    const header = ['Показатель / Регион', ...regions].join('\t');
    const tableText = [header, ...rows].join('\n');

    // Сохраняем в кнопке копирования
    const btn = container.querySelector('.copy-chart-data-btn');
    if (btn) btn.dataset.text = tableText;

}
