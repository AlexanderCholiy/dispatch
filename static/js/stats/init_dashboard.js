import {
    loadStatisticsAll,
    loadStatisticsFromDate
} from './data/stats_data_from_api.js';

import {
    renderAllIncidentsChart
} from './charts/all_incidents_chart.js';

async function initDashboard() {
    try {
        // 🔵 Все инциденты
        const rootStyles = getComputedStyle(document.documentElement);
        const allStats = await loadStatisticsAll();

        renderAllIncidentsChart(
            document.getElementById('all-incidents-chart'),
            allStats,
            {
                title: 'Инциденты за всё время',
                label: 'Всего инцидентов',
                valueKey: 'total_incidents',
                color: rootStyles.getPropertyValue('--blue-color').trim() || '#3b82f6'
            }
        );

        // 🔴 Открытые инциденты за период
        const periodStats = await loadStatisticsFromDate('2025-11-01');

        renderAllIncidentsChart(
            document.getElementById('all-incidents-chart-period'),
            periodStats,
            {
                title: 'Инциденты с 01.11.2025',
                label: 'Открытые инциденты',
                valueKey: 'total_open_incidents',
                color: rootStyles.getPropertyValue('--red-color').trim() || '#c02f1cff'
            }
        );

    } catch (error) {
        console.error('Dashboard init error:', error);
    }
}

initDashboard();
