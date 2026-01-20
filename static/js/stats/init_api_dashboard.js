import { loadStatisticsFromDate } from './data/stats_data_from_api.js';

import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';
import { renderDailyIncidentsChart } from './charts/daily_incidents_chart.js';

import { getThemeVars } from './charts/utils.js';

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
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
}

export async function initApiDashboard() {
    try {
        const startDate = getFirstDayOfPreviousMonth();
        const formattedDate = formatDateDDMMYYYY(startDate);
        const stats = await loadStatisticsFromDate(startDate);

        const theme = getThemeVars();

        // -----------------------------
        // Общий заголовок
        // -----------------------------
        const container = document.querySelector('.stats');
        let h3 = container.querySelector('.dashboard-group-title');
        if (!h3) {
            h3 = document.createElement('h3');
            h3.className = 'dashboard-group-title';
            container.prepend(h3);
        }
        h3.textContent = `Статистика по инцидентам с ${formattedDate}`;

        // -----------------------------
        // Daily incidents
        // -----------------------------
        renderDailyIncidentsChart(
            document.getElementById('daily-incidents-chart'),
            stats,
            {
                title: `Динамика инцидентов по дням`
            }
        );

        // -----------------------------
        // Закрытые
        // -----------------------------
        renderAllIncidentsChart(
            document.getElementById('all-closed-incidents-chart'),
            stats,
            {
                title: `Закрытые инциденты с ${formattedDate}`,
                datasets: [
                    {
                        label: 'Всего закрытых',
                        valueKey: 'total_closed_incidents',
                        colorVar: '--green-color'
                    },
                    {
                        label: 'Без питания',
                        valueKey: 'closed_incidents_with_power_issue',
                        colorVar: '--gray-color'
                    }
                ]
            }
        );

        // -----------------------------
        // Открытые
        // -----------------------------
        renderAllIncidentsChart(
            document.getElementById('all-open-incidents-chart'),
            stats,
            {
                title: `Открытые инциденты с ${formattedDate}`,
                datasets: [
                    {
                        label: 'Всего открытых',
                        valueKey: 'total_open_incidents',
                        colorVar: '--blue-color'
                    },
                    {
                        label: 'Без питания',
                        valueKey: 'open_incidents_with_power_issue',
                        colorVar: '--gray-color'
                    }
                ]
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

        stats.forEach(region => {
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

initApiDashboard();
