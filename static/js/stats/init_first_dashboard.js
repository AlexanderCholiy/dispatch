import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';

function getCssVar(name, fallback = '#999') {
    return (
        getComputedStyle(document.documentElement)
            .getPropertyValue(name)
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
    const mutedColor = getCssVar('--extra-color');

    // -----------------------------
    // Общий заголовок перед графиками
    // -----------------------------
    const container = document.querySelector('.stats');
    const h3 = document.createElement('h3');
    h3.className = 'dashboard-group-title';
    h3.textContent = 'Статистика по инцидентам';
    container.prepend(h3);

    // -----------------------------
    // Закрытые инциденты
    // -----------------------------
    renderAllIncidentsChart(
        document.getElementById('all-closed-incidents-chart'),
        [], // пустые данные
        {
            datasets: [
                {
                    label: 'Всего закрытых',
                    valueKey: 'total_closed_incidents',
                    color: mutedColor
                },
                {
                    label: 'Без питания',
                    valueKey: 'closed_incidents_with_power_issue',
                    color: mutedColor
                }
            ]
        }
    );

    // -----------------------------
    // Открытые инциденты
    // -----------------------------
    renderAllIncidentsChart(
        document.getElementById('all-open-incidents-chart'),
        [], // пустые данные
        {
            datasets: [
                {
                    label: 'Всего открытых',
                    valueKey: 'total_open_incidents',
                    color: mutedColor
                },
                {
                    label: 'Без питания',
                    valueKey: 'open_incidents_with_power_issue',
                    color: mutedColor
                }
            ]
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
