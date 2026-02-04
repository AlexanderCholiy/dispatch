import { createDailyIncidentsChart, updateDailyIncidentsChartColors } from './charts/daily_incidents.js';
import { createAllIncidentsChart, updateAllIncidentsChartColors } from './charts/all_incidents.js';
import { createSlaDonutChart, updateSlaDonutChartColors } from './charts/sla_donut.js';
import { getDatesSincePreviousMonth } from './charts_utils.js';
import { getChartColors, observeThemeChange } from './theme_colors.js';
import { updateCopyButton, updateSlaCopyData } from './data/copy_chart_data.js';
import { startStatisticsPolling } from './dashboard_api_updater.js';
import { startStatisticsWebSocket } from './dashboard_ws_updater.js';

if (window.Chart && window.ChartZoom) {
    Chart.register(window.ChartZoom);
}

window.dashboardCharts = {};

document.addEventListener('DOMContentLoaded', () => {
    const colors = getChartColors();

    const regionColors = [
        colors.pink, colors.cyan, colors.blue, colors.red,
        colors.yellow, colors.brown, colors.gray, colors.magenta, colors.green,
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
        { labels: getDatesSincePreviousMonth(), datasets: dailyDatasets }
    );
    window.dashboardCharts.daily = dailyChart;
    updateCopyButton('daily-chart-card', dailyChart, 'Дата/Регион');

    const MACROREGION_LABELS = ['МР-1','МР-2','МР-3','МР-4','МР-5','МР-6','МР-7','МР-8','МР-9'];

    const closedChart = createAllIncidentsChart(
        document.getElementById('all-closed-incidents-chart').getContext('2d'),
        { labels: MACROREGION_LABELS, datasets: [{ label: 'Всего', data: [], backgroundColor: colors.green }, { label: 'Без питания', data: [], backgroundColor: colors.gray }] },
        'Закрытые'
    );
    window.dashboardCharts.closed = closedChart;
    updateCopyButton('closed-chart-card', closedChart, 'Регион/Количество инцидентов');

    const openChart = createAllIncidentsChart(
        document.getElementById('all-open-incidents-chart').getContext('2d'),
        { labels: MACROREGION_LABELS, datasets: [{ label: 'Всего', data: [], backgroundColor: colors.blue }, { label: 'Без питания', data: [], backgroundColor: colors.gray }] },
        'Открытые'
    );
    window.dashboardCharts.open = openChart;
    updateCopyButton('open-chart-card', openChart, 'Регион/Количество инцидентов');

    const typesDatasets = [
        { label: 'Авария по питанию', color: colors.blue },
        { label: 'Инцидент по конструктиву / территорией АМС', color: colors.red },
        { label: 'Инцидент / запрос гос. органов', color: colors.green },
        { label: 'Авария ВОЛС', color: colors.yellow },
        { label: 'Угроза гибели / гибель объекта', color: colors.gray },
        { label: 'Запрос на организацию доступа к объекту', color: colors.cyan },
    ];

    const typesChart = createAllIncidentsChart(
        document.getElementById('types-incidents-chart').getContext('2d'),
        { labels: MACROREGION_LABELS, datasets: typesDatasets.map(d => ({ label: d.label, data: [], backgroundColor: d.color })) },
        'Классификация аварий',
        true,
    );
    window.dashboardCharts.types = typesChart;
    updateCopyButton('types-chart-card', typesChart, 'Регион/Тип аварии');

    const initSlaSkeleton = (containerId, bar_title) => {
        const container = document.getElementById(containerId);
        const charts = [];

        // Очищаем всё кроме блока с кнопками
        container.querySelectorAll(':scope > *:not(.chart-utils)').forEach(el => el.remove());

        const titleEl = document.createElement('p');
        titleEl.className = 'sla-title';
        titleEl.textContent = bar_title;
        container.appendChild(titleEl);

        const grid = document.createElement('div');
        grid.className = 'sla-grid';
        container.appendChild(grid);

        for (let i = 1; i <= 9; i++) {
            const item = document.createElement('div');
            item.className = 'sla-item';

            const canvas = document.createElement('canvas');
            item.appendChild(canvas);
            grid.appendChild(item);

            const chart = createSlaDonutChart(canvas.getContext('2d'), { title: `МР-${i}`, single: true, data: [], datasetColors: [], total: 0 });
            charts.push(chart);
        }

        const copyBtn = container.querySelector('.copy-chart-data-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                if (window.dashboardCharts.lastSlaData) {
                    // Определяем тип данных на основе ID контейнера
                    let type = 'avr'; // значение по умолчанию
                    if (containerId.includes('rvr')) {
                        type = 'rvr';
                    } else if (containerId.includes('dgu')) {
                        type = 'dgu';
                    }

                    // Обновляем данные перед копированием
                    updateSlaCopyData(containerId, window.dashboardCharts.lastSlaData, type);
                    
                    // Копируем в буфер
                    navigator.clipboard.writeText(copyBtn.dataset.text || '');
                }
            });
        }

        return charts;
    };

    window.dashboardCharts.sla = {
        avr: initSlaSkeleton('avr-sla-grid', 'SLA АВР'),
        rvr: initSlaSkeleton('rvr-sla-grid', 'SLA РВР'),
        dgu: initSlaSkeleton('dgu-sla-grid', 'ВРТ РВР'),
    };

    // Для теста:
    // startStatisticsPolling(window.dashboardCharts);

    startStatisticsWebSocket(window.dashboardCharts);

    observeThemeChange(() => {
        const colors = getChartColors();
        updateDailyIncidentsChartColors(window.dashboardCharts.daily);
        updateAllIncidentsChartColors(window.dashboardCharts.closed, [colors.green, colors.gray]);
        updateAllIncidentsChartColors(window.dashboardCharts.open, [colors.blue, colors.gray]);
        updateAllIncidentsChartColors(window.dashboardCharts.types, [colors.blue, colors.red, colors.green, colors.yellow, colors.gray, colors.cyan]);
        updateSlaDonutChartColors(window.dashboardCharts.sla.avr);
        updateSlaDonutChartColors(window.dashboardCharts.sla.rvr);
        updateSlaDonutChartColors(window.dashboardCharts.sla.dgu);
    });
});
