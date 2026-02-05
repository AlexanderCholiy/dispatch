import { adaptDailyIncidents } from './statistics_adapter.js';
import { adaptSla } from './sla_adapter.js';
import { getChartColors } from '../theme_colors.js';

/* ---------- DAILY LINE ---------- */
export function updateDailyChart(chart, apiData) {
    if (!chart) return;

    const adapted = adaptDailyIncidents(apiData);

    chart.data.labels = adapted.labels;

    adapted.datasets.forEach((incoming, idx) => {
        const tension = 0.2; // плавность линий

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

export function updateSubtypesChart(chart, apiData, categoryName, subtypeLabels, macroregionLabels) {
    const datasets = chart.data.datasets;

    // Обнуляем данные
    datasets.forEach(ds => ds.data = []);

    // Формируем данные по макрорегионам из API
    macroregionLabels.forEach(regionLabel => {
        const regionData = apiData.find(r => r.macroregion === regionLabel);
        const stats = regionData?.incident_subtype_stats?.[categoryName] || {};

        subtypeLabels.forEach((label, idx) => {
            datasets[idx].data.push(stats[label] ?? 0);
        });
    });

    chart.data.labels = macroregionLabels;
    chart.update();
}

/* ---------- SLA ---------- */
export function updateSlaCharts(charts, apiData, type) {
    if (!charts?.length) return;

    const colors = getChartColors();

    const slaConfig = {
        avr: {
            labels: [
                'Просрочено',
                'Закрыто вовремя',
                'Менее часа',
                'В работе',
            ],
            colors: [
                colors.red,
                colors.green,
                colors.yellow,
                colors.blue,
            ],
        },
        rvr: {
            labels: [
                'Просрочено',
                'Закрыто вовремя',
                'Менее часа',
                'В работе',
            ],
            colors: [
                colors.red,
                colors.green,
                colors.yellow,
                colors.blue,
            ],
        },
        dgu: {
            labels: [
                'Более 15 дней',
                'Закрыт за 15 дней',
                'Менее 15 дней',
                'Менее 12 часов',
            ],
            colors: [
                colors.red,
                colors.green,
                colors.yellow,
                colors.blue,
            ],
        },
    };

    const { labels, colors: slaColors } =
        slaConfig[type] ?? slaConfig.avr;

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
            chart.data.labels = labels;
            chart.data.datasets[0].data = data;
            chart.data.datasets[0].backgroundColor = slaColors;

            chart.data.datasets[0].borderWidth = nonZeroCount > 1 ? 1 : 0;
            chart.data.datasets[0].borderColor = data.map(v =>
                v > 0 && nonZeroCount > 1 ? colors.bg : 'transparent'
            );

            chart.$hasData = true;
        }

        chart.$total = total;

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
