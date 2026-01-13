import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';

function getThemeColor(varName, fallback) {
    return (
        getComputedStyle(document.documentElement)
            .getPropertyValue(varName)
            .trim() || fallback
    );
}

function renderEmptySlaBlock(containerId, titleText) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    const title = document.createElement('h3');
    title.className = 'dashboard-group-title';
    title.textContent = titleText;
    container.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'sla-grid';
    container.appendChild(grid);

    for (let i = 0; i < 3; i++) {
        const card = document.createElement('div');
        card.className = 'sla-card';
        card.innerHTML = '<canvas></canvas>';
        grid.appendChild(card);

        renderSlaDonut(
            card.querySelector('canvas'),
            'Загрузка…',
            [0, 0, 0, 0]
        );
    }
}

export function initFirstDashboard() {
    // -----------------------------
    // Основные графики (skeleton)
    // -----------------------------
    renderAllIncidentsChart(
        document.getElementById('all-incidents-chart'),
        [],
        {
            title: 'Инциденты за всё время',
            label: 'Всего инцидентов',
            valueKey: 'total_incidents',
            color: getThemeColor('--blue-color', '#3b82f6')
        }
    );

    renderAllIncidentsChart(
        document.getElementById('all-incidents-chart-period'),
        [],
        {
            title: 'Инциденты за период',
            label: 'Открытые инциденты',
            valueKey: 'total_open_incidents',
            color: getThemeColor('--red-color', '#ef4444')
        }
    );

    // -----------------------------
    // SLA skeleton
    // -----------------------------
    renderEmptySlaBlock('avr-sla-grid', 'SLA АВР');
    renderEmptySlaBlock('rvr-sla-grid', 'SLA РВР');
}

// автоинициализация
initFirstDashboard();
