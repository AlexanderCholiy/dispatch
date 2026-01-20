import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';
import { renderDailyIncidentsChart } from './charts/daily_incidents_chart.js';
import { getThemeVars } from './charts/utils.js'; // Используем общую функцию темы

if (window.Chart && window.ChartZoom) {
    Chart.register(window.ChartZoom);
}

function renderEmptySlaBlock(containerId, titleText) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = ''; // Очистка

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


// Генерирует массив дат от 1-го числа предыдущего месяца до сегодня
function getSkeletonLabels() {
    const labels = [];
    const today = new Date();
    
    // 1-е число предыдущего месяца по местному времени
    const startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);

    let currentDate = new Date(startDate);
    
    // Сбрасываем время у today в 00:00, чтобы сравнение в while было корректным
    const targetDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    while (currentDate <= targetDate) {
        // Форматируем дату в YYYY-MM-DD по локальному времени
        const year = currentDate.getFullYear();
        const month = String(currentDate.getMonth() + 1).padStart(2, '0');
        const day = String(currentDate.getDate()).padStart(2, '0');
        
        labels.push(`${year}-${month}-${day}`);
        
        // Переходим к следующему дню
        currentDate.setDate(currentDate.getDate() + 1);
    }
    
    return labels;
}

export function initFirstDashboard() {
    const theme = getThemeVars();
    const mutedColor = theme.gray

    // -----------------------------
    // Общий заголовок (проверка на дубликаты)
    // -----------------------------
    const container = document.querySelector('.stats');
    if (!container) return;

    // Удаляем старый заголовок, если он был, чтобы не дублировать
    const oldTitle = container.querySelector('.dashboard-group-title.main-title');
    if (oldTitle) oldTitle.remove();

    const h3 = document.createElement('h3');
    h3.className = 'dashboard-group-title main-title';
    h3.textContent = 'Статистика по инцидентам';
    container.prepend(h3);

    // -----------------------------
    // Daily incidents (skeleton)
    // -----------------------------
    const dailyCanvas = document.getElementById('daily-incidents-chart');
    if (dailyCanvas) {
        const dateRange = getSkeletonLabels();
        renderDailyIncidentsChart(dailyCanvas, [], {
            title: 'Загрузка динамики инцидентов по дням…',
            empty: true,
            skeletonLabels: dateRange,
            yMin: 0,
            yMax: 10,
            lineColor: mutedColor
        });
    }

    // -----------------------------
    // Закрытые инциденты (скелетон)
    // -----------------------------
    const closedCanvas = document.getElementById('all-closed-incidents-chart');
    if (closedCanvas) {
        renderAllIncidentsChart(closedCanvas, [], {
            datasets: [
                { label: 'Всего закрытых', valueKey: 'total_closed_incidents', color: mutedColor },
                { label: 'Без питания', valueKey: 'closed_incidents_with_power_issue', color: mutedColor }
            ]
        });
    }

    // -----------------------------
    // Открытые инциденты (скелетон)
    // -----------------------------
    const openCanvas = document.getElementById('all-open-incidents-chart');
    if (openCanvas) {
        renderAllIncidentsChart(openCanvas, [], {
            datasets: [
                { label: 'Всего открытых', valueKey: 'total_open_incidents', color: mutedColor },
                { label: 'Без питания', valueKey: 'open_incidents_with_power_issue', color: mutedColor }
            ]
        });
    }

    // -----------------------------
    // SLA skeleton
    // -----------------------------
    renderEmptySlaBlock('avr-sla-grid', 'SLA АВР');
    renderEmptySlaBlock('rvr-sla-grid', 'SLA РВР');
}

// Автоинициализация при загрузке
document.addEventListener('DOMContentLoaded', initFirstDashboard);
