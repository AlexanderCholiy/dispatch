import { adaptDailyIncidents } from './data/statistics_adapter.js';
import { adaptSla } from './data/sla_adapter.js';
import { getFirstDayOfPreviousMonth, formatDate } from './charts_utils.js';
import { getChartColors } from './theme_colors.js';

let isFetching = false;

async function fetchStatistics(startDate) {
    const res = await fetch(`/api/v1/report/statistics/?start_date=${startDate}`);
    if (!res.ok) throw new Error('Statistics API error');
    return res.json();
}

/* ---------- DAILY LINE ---------- */

function updateDailyChart(chart, apiData) {
    if (!chart) return;

    const adapted = adaptDailyIncidents(apiData);

    chart.data.labels = adapted.labels;

    adapted.datasets.forEach((incoming, idx) => {
        if (!chart.data.datasets[idx]) {
            // если датасет новый — добавляем и ставим tension
            chart.data.datasets[idx] = { ...incoming, tension: 0.3 };
        } else {
            // обновляем существующий датасет
            chart.data.datasets[idx].data = incoming.data;
            chart.data.datasets[idx].label = incoming.label;
            chart.data.datasets[idx].tension = 0.3; // сохраняем плавность
        }
    });

    chart.update('none');
}

/* ---------- BAR HELPERS ---------- */

function updateBarChart(chart, apiData, fields) {
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
function updateSlaCharts(charts, apiData, type) {
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

/* ---------- POLLING ---------- */

export function startStatisticsPolling(
    dailyChart,
    closedChart,
    openChart,
    slaCharts,
    interval = 10_000
) {
    const startDate = formatDate(getFirstDayOfPreviousMonth());

    const load = async () => {
        if (isFetching) return;
        isFetching = true;

        try {
            const apiData = await fetchStatistics(startDate);

            // DAILY
            updateDailyChart(dailyChart, apiData);

            // CLOSED BAR
            updateBarChart(closedChart, apiData, [
                'total_closed_incidents',
                'closed_incidents_with_power_issue',
            ]);

            // OPEN BAR
            updateBarChart(openChart, apiData, [
                'total_open_incidents',
                'open_incidents_with_power_issue',
            ]);

            // SLA
            updateSlaCharts(slaCharts.avr, apiData, 'avr');
            updateSlaCharts(slaCharts.rvr, apiData, 'rvr');

        } catch (e) {
            console.error('Polling error:', e);
        } finally {
            isFetching = false;
        }
    };

    load();
    return setInterval(load, interval);
}
