import { adaptDailyIncidents } from './statistics_adapter.js';
import { adaptSla } from './sla_adapter.js';
import { getChartColors } from '../theme_colors.js';

/* ---------- DAILY LINE ---------- */
export function updateDailyChart(chart, apiData) {
    if (!chart) return;

    const adapted = adaptDailyIncidents(apiData);

    chart.data.labels = adapted.labels;

    adapted.datasets.forEach((incoming, idx) => {
        const tension = 0.3; // плавность линий

        if (!chart.data.datasets[idx]) {
            // новый датасет — добавляем с tension
            chart.data.datasets[idx] = { ...incoming, tension };
        } else {
            // обновляем существующий датасет
            chart.data.datasets[idx].data = incoming.data;
            chart.data.datasets[idx].label = incoming.label;
            chart.data.datasets[idx].tension = tension;
        }
    });

    // плавное обновление без анимации дергания осей
    chart.update('none');
}

/* ---------- BAR HELPERS ---------- */
export function updateBarChart(chart, apiData, fields) {
    if (!chart) return;

    // 1. labels из API
    chart.data.labels = apiData.map(item => item.macroregion);

    // 2. данные по датасетам
    chart.data.datasets.forEach((dataset, datasetIdx) => {
        dataset.data = apiData.map(
            item => item[fields[datasetIdx]] ?? 0
        );
    });

    chart.update('none');
}

/* ---------- SLA ---------- */
export function updateSlaCharts(charts, apiData, type) {
    if (!charts?.length) return;

    const colors = getChartColors();
    const slaColors = [
        colors.red,     // Просрочено
        colors.green,   // Закрыто вовремя
        colors.yellow,  // Менее часа
        colors.blue,    // В работе
    ];

    charts.forEach((chart, idx) => {
        const apiItem = apiData[idx];
        if (!chart || !apiItem) return;

        chart.options.plugins.title.text =
            apiItem.macroregion ?? `МР-${idx + 1}`;

        const data = adaptSla(apiItem, type);
        const total = data.reduce((a, b) => a + b, 0);

        const nonZeroCount = data.filter(v => v > 0).length;

        if (total === 0) {
            chart.data.labels = ['Нет данных'];
            chart.data.datasets[0].data = [1];
            chart.data.datasets[0].backgroundColor = [colors.gray];
            chart.data.datasets[0].borderColor = ['transparent'];
            chart.data.datasets[0].borderWidth = 0;
            chart.$hasData = false;
        } else {
            chart.data.labels = [
                'Просрочено',
                'Закрыто вовремя',
                'Менее часа',
                'В работе',
            ];
            chart.data.datasets[0].data = data;
            chart.data.datasets[0].backgroundColor = slaColors;

            chart.data.datasets[0].borderWidth = nonZeroCount > 1 ? 1 : 0;
            chart.data.datasets[0].borderColor = data.map(v =>
                v > 0 && nonZeroCount > 1 ? colors.bg : 'transparent'
            );

            chart.$hasData = true;
        }

        chart.$total = total;

        // Обновляем tooltip hover цвета, чтобы сегменты не краснели
        chart.options.plugins.tooltip.callbacks = {
            label: (tooltipItem) => {
                const value = chart.data.datasets[0].data[tooltipItem.dataIndex];
                const label = chart.data.labels[tooltipItem.dataIndex];
                return `${label}: ${value}`;
            }
        };

        chart.update();
    });
}
