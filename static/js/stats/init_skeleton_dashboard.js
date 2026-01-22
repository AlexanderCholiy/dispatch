import { createDailyIncidentsChart, updateDailyIncidentsChartColors } from './charts/daily_incidents.js';
import { createAllIncidentsChart, updateAllIncidentsChartColors } from './charts/all_incidents.js';
import { createSlaDonutChart, updateSlaDonutChartColors } from './charts/sla_donut.js';
import { getDatesSincePreviousMonth, getFirstDayOfPreviousMonth, formatDateRu } from './charts_utils.js';
import { startStatisticsPolling } from './dashboard_api_updater.js';
import { getChartColors, observeThemeChange } from './theme_colors.js';
import { startStatisticsWebSocket } from './dashboard_ws_updater.js';

if (window.Chart && window.ChartZoom) {
    Chart.register(window.ChartZoom);
}

window.dashboardCharts = {};

document.addEventListener('DOMContentLoaded', () => {
    const colors = getChartColors();

    /* ---------- DASHBOARD TITLE ---------- */
    const startDate = getFirstDayOfPreviousMonth();
    const formattedDate = formatDateRu(startDate);
    const titleEl = document.createElement('p');

    titleEl.className = 'dashboard-title';
    titleEl.textContent = `Статистика по инцидентам от ${formattedDate}`;

    const root = document.getElementById('dashboard-root') || document.body;
    root.prepend(titleEl);

    /* ---------- DAILY LINE ---------- */

    const regionColors = [
        colors.pink,
        colors.cyan,
        colors.blue,
        colors.red,
        colors.yellow,
        colors.brown,
        colors.gray,
        colors.magenta,
        colors.green,
    ];

    const dailyDatasets = regionColors.map((color, idx) => ({
        label: `МР-${idx + 1}`,
        data: [],
        borderColor: color,
        backgroundColor: color,
        fill: false,
    }));

    const dailyChart = createDailyIncidentsChart(
        document.getElementById('daily-incidents-chart').getContext('2d'),
        {
            labels: getDatesSincePreviousMonth(),
            datasets: dailyDatasets,
        }
    );

    window.dashboardCharts.daily = dailyChart;

    /* ---------- CLOSED BAR ---------- */
    const MACROREGION_LABELS = [
        'МР-1', 'МР-2', 'МР-3', 'МР-4', 'МР-5',
        'МР-6', 'МР-7', 'МР-8', 'МР-9',
    ];

    const closedDatasets = [
        { label: 'Всего', color: colors.green },
        { label: 'Без питания', color: colors.gray },
    ];

    const closedChart = createAllIncidentsChart(
        document.getElementById('all-closed-incidents-chart').getContext('2d'),
        {
            labels: MACROREGION_LABELS,
            datasets: closedDatasets.map(d => ({
                label: d.label,
                data: [],
                backgroundColor: d.color,
            }))
        },
        'Закрытые инциденты'
    );

    window.dashboardCharts.closed = closedChart;

    /* ---------- OPEN BAR ---------- */

    const openDatasets = [
        { label: 'Всего', color: colors.blue },
        { label: 'Без питания', color: colors.gray },
    ];

    const openChart = createAllIncidentsChart(
        document.getElementById('all-open-incidents-chart').getContext('2d'),
        {
            labels: MACROREGION_LABELS,
            datasets: openDatasets.map(d => ({
                label: d.label,
                data: [],
                backgroundColor: d.color,
            }))
        },
        'Открытые инциденты'
    );

    window.dashboardCharts.open = openChart;

    /* ---------- SLA DONUTS (SKELETON) ---------- */
    const initSlaSkeleton = (containerId, bar_title) => {
        const container = document.getElementById(containerId);
        const charts = [];

        // очищаем контейнер (на случай повторной инициализации)
        container.innerHTML = '';

        /* ---- TITLE ---- */
        const titleEl = document.createElement('p');
        titleEl.className = 'sla-title';
        titleEl.textContent = bar_title;
        container.appendChild(titleEl);

        /* ---- GRID ---- */
        const grid = document.createElement('div');
        grid.className = 'sla-grid';
        container.appendChild(grid);

        for (let i = 1; i <= 9; i++) {
            // ОБЁРТКА
            const item = document.createElement('div');
            item.className = 'sla-item';

            // CANVAS
            const canvas = document.createElement('canvas');
            item.appendChild(canvas);

            // добавляем в grid
            grid.appendChild(item);

            // создаём график
            const chart = createSlaDonutChart(
                canvas.getContext('2d'),
                {
                    title: `МР-${i}`,
                    single: true,
                    data: [],
                    datasetColors: [],
                    total: 0
                }
            );

            charts.push(chart);
        }

        return charts;
    };

    window.dashboardCharts.sla = {
        avr: initSlaSkeleton('avr-sla-grid', 'SLA АВР'),
        rvr: initSlaSkeleton('rvr-sla-grid', 'SLA РВР'),
    };

    // Обновление данных через API:
    startStatisticsPolling(
        window.dashboardCharts.daily,
        window.dashboardCharts.closed,
        window.dashboardCharts.open,
        window.dashboardCharts.sla
    );

    // Обновление данных через WS:
    // startStatisticsWebSocket(window.dashboardCharts);

    /* ---------- THEME CHANGE ---------- */

    observeThemeChange(() => {
        const colors = getChartColors();

        updateDailyIncidentsChartColors(window.dashboardCharts.daily);

        updateAllIncidentsChartColors(
            window.dashboardCharts.closed,
            [colors.green, colors.gray]
        );

        updateAllIncidentsChartColors(
            window.dashboardCharts.open,
            [colors.blue, colors.gray]
        );

        updateSlaDonutChartColors(
            window.dashboardCharts.sla.avr,
        );

        updateSlaDonutChartColors(
            window.dashboardCharts.sla.rvr,
        );
    });
});
