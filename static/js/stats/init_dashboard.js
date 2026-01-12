import {
    loadStatisticsAll,
    loadStatisticsFromDate
} from './data/stats_data_from_api.js';

import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';

async function initDashboard() {
    try {
        const rootStyles = getComputedStyle(document.documentElement);
        const allStats = await loadStatisticsAll();

        // -----------------------------
        // Все инциденты
        // -----------------------------
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

        // Открытые инциденты за период
        const periodStats = await loadStatisticsFromDate('2025-11-01');

        renderAllIncidentsChart(
            document.getElementById('all-incidents-chart-period'),
            periodStats,
            {
                title: 'Инциденты с 01.11.2025',
                label: 'Открытые инциденты с 01.11.2025',
                valueKey: 'total_open_incidents',
                color: rootStyles.getPropertyValue('--red-color').trim() || '#c02f1cff'
            }
        );

        // -----------------------------
        // SLA Сетки
        // -----------------------------
        const avrGridContainer = document.getElementById('avr-sla-grid');
        const rvrGridContainer = document.getElementById('rvr-sla-grid');

        // Добавляем динамические заголовки
        const avrTitle = document.createElement('h3');
        avrTitle.className = 'dashboard-group-title';
        avrTitle.textContent = 'SLA АВР с 01.11.2025';
        avrGridContainer.appendChild(avrTitle);

        const rvrTitle = document.createElement('h3');
        rvrTitle.className = 'dashboard-group-title';
        rvrTitle.textContent = 'SLA РВР с 01.11.2025';
        rvrGridContainer.appendChild(rvrTitle);

        // Создаём отдельные grid-контейнеры для карточек
        const avrGrid = document.createElement('div');
        avrGrid.className = 'sla-grid';
        avrGridContainer.appendChild(avrGrid);

        const rvrGrid = document.createElement('div');
        rvrGrid.className = 'sla-grid';
        rvrGridContainer.appendChild(rvrGrid);

        // -----------------------------
        // Добавление карточек
        // -----------------------------
        periodStats.forEach(region => {
            // АВР
            const avrCard = document.createElement('div');
            avrCard.className = 'sla-card';
            avrCard.innerHTML = `
                <canvas></canvas>
            `;
            avrGrid.appendChild(avrCard);

            renderSlaDonut(
                avrCard.querySelector('canvas'),
                region.macroregion,
                [
                    region.sla_avr_expired_count,
                    region.sla_avr_closed_on_time_count,
                    region.sla_avr_less_than_hour_count,
                    region.sla_avr_in_progress_count
                ]
            );

            // РВР
            const rvrCard = document.createElement('div');
            rvrCard.className = 'sla-card';
            rvrCard.innerHTML = `
                <canvas></canvas>
            `;
            rvrGrid.appendChild(rvrCard);

            renderSlaDonut(
                rvrCard.querySelector('canvas'),
                region.macroregion,
                [
                    region.sla_rvr_expired_count,
                    region.sla_rvr_closed_on_time_count,
                    region.sla_rvr_less_than_hour_count,
                    region.sla_rvr_in_progress_count
                ]
            );
        });

    } catch (error) {
        console.error('Dashboard init error:', error);
    }
}

initDashboard();
