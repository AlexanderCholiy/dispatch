import {
    loadStatisticsAll,
    loadStatisticsFromDate
} from './data/stats_data_from_api.js';

import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';

function getFirstDayOfPreviousMonth() {
    const now = new Date();
    const year = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
    const month = now.getMonth() === 0 ? 12 : now.getMonth();
    return `${year}-${month.toString().padStart(2, '0')}-01`;
}

function formatDateDDMMYYYY(dateStr) {
    const [year, month] = dateStr.split('-');
    return `01.${month}.${year}`;
}

function clearContainer(id) {
    document.getElementById(id).innerHTML = '';
}

export async function initApiDashboard() {
    try {
        const rootStyles = getComputedStyle(document.documentElement);

        // -----------------------------
        // Все инциденты
        // -----------------------------
        const allStats = await loadStatisticsAll();

        renderAllIncidentsChart(
            document.getElementById('all-incidents-chart'),
            allStats,
            {
                title: 'Инциденты за всё время',
                label: 'Всего инцидентов',
                valueKey: 'total_incidents',
                color: rootStyles.getPropertyValue('--blue-color').trim()
            }
        );

        // -----------------------------
        // Инциденты за период
        // -----------------------------
        const startDate = getFirstDayOfPreviousMonth();
        const formattedDate = formatDateDDMMYYYY(startDate);

        const periodStats = await loadStatisticsFromDate(startDate);

        renderAllIncidentsChart(
            document.getElementById('all-incidents-chart-period'),
            periodStats,
            {
                title: `Инциденты с ${formattedDate}`,
                label: 'Открытые инциденты',
                valueKey: 'total_open_incidents',
                color: rootStyles.getPropertyValue('--red-color').trim()
            }
        );

        // -----------------------------
        // SLA
        // -----------------------------
        clearContainer('avr-sla-grid');
        clearContainer('rvr-sla-grid');

        const avrContainer = document.getElementById('avr-sla-grid');
        const rvrContainer = document.getElementById('rvr-sla-grid');

        const avrTitle = document.createElement('h3');
        avrTitle.className = 'dashboard-group-title';
        avrTitle.textContent = `SLA АВР с ${formattedDate}`;
        avrContainer.appendChild(avrTitle);

        const rvrTitle = document.createElement('h3');
        rvrTitle.className = 'dashboard-group-title';
        rvrTitle.textContent = `SLA РВР с ${formattedDate}`;
        rvrContainer.appendChild(rvrTitle);

        const avrGrid = document.createElement('div');
        avrGrid.className = 'sla-grid';
        avrContainer.appendChild(avrGrid);

        const rvrGrid = document.createElement('div');
        rvrGrid.className = 'sla-grid';
        rvrContainer.appendChild(rvrGrid);

        periodStats.forEach(region => {
            const avrCard = document.createElement('div');
            avrCard.className = 'sla-card';
            avrCard.innerHTML = '<canvas></canvas>';
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

            const rvrCard = document.createElement('div');
            rvrCard.className = 'sla-card';
            rvrCard.innerHTML = '<canvas></canvas>';
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

    } catch (e) {
        console.error('Dashboard init error:', e);
    }
}

// автоинициализация
initApiDashboard();
