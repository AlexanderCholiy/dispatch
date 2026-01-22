import { getFirstDayOfPreviousMonth, formatDate } from './charts_utils.js';
import { updateDailyChart, updateBarChart, updateSlaCharts } from './data/charts_updater.js';

let isFetching = false;
let pollingInterval = null;
let lastErrorMessage = null; // последнее сообщение об ошибке

async function fetchStatistics(startDate, endDate = null) {
    let url = `/api/v1/report/statistics/?start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error('Statistics API error');
    return res.json();
}

function updateCharts(apiData, dailyChart, closedChart, openChart, slaCharts) {
    updateDailyChart(dailyChart, apiData);

    updateBarChart(closedChart, apiData, [
        'total_closed_incidents',
        'closed_incidents_with_power_issue',
    ]);

    updateBarChart(openChart, apiData, [
        'total_open_incidents',
        'open_incidents_with_power_issue',
    ]);

    updateSlaCharts(slaCharts.avr, apiData, 'avr');
    updateSlaCharts(slaCharts.rvr, apiData, 'rvr');
}

function showMessage(text, type = 'error', messagesContainer) {
    if (lastErrorMessage === text) return;
    lastErrorMessage = text;

    const msg = document.createElement('div');
    msg.className = `message alert-${type}`;
    msg.innerText = text;
    messagesContainer.appendChild(msg);

    setTimeout(() => {
        msg.remove();
        lastErrorMessage = null;
    }, 5000);
}

export function startStatisticsPolling(
    dailyChart,
    closedChart,
    openChart,
    slaCharts,
    interval = 10_000
) {
    const startInput = document.getElementById('start-date');
    const endInput = document.getElementById('end-date');
    const applyBtn = document.getElementById('apply-period');
    const resetBtn = document.getElementById('reset-period');
    const messagesContainer = document.querySelector('.messages-container');

    // ---------- Установки умолчаний ----------
    const defaultStart = formatDate(getFirstDayOfPreviousMonth());
    const defaultEnd = ''; // пусто = до сегодня
    startInput.value = defaultStart;
    endInput.value = defaultEnd;

    // Ограничение: дата конца не может быть больше сегодняшней
    const today = new Date().toISOString().split('T')[0];
    endInput.max = today;

    // Последние подтверждённые пользователем даты
    let confirmedStart = defaultStart;
    let confirmedEnd = defaultEnd || null;

    // ---------- Загрузка данных ----------
    async function load(startDate, endDate) {
        if (isFetching) return;
        isFetching = true;

        try {
            const apiData = await fetchStatistics(startDate, endDate);

            if (apiData.error) {
                showMessage(apiData.error, 'error', messagesContainer);
                return;
            }

            updateCharts(apiData, dailyChart, closedChart, openChart, slaCharts);

        } catch (e) {
            console.error('Polling error:', e);
            showMessage('Ошибка при получении статистики', 'error', messagesContainer);
        } finally {
            isFetching = false;
        }
    }

    // ---------- Первая предзагрузка с дефолтными датами ----------
    load(confirmedStart, confirmedEnd);

    // ---------- Применить выбранный период ----------
    applyBtn.addEventListener('click', () => {
        const startDate = startInput.value;
        const endDate = endInput.value || null;

        // Валидация только при подтверждении пользователем
        if (endDate && startDate > endDate) {
            showMessage('Дата начала не может быть больше даты конца', 'warning', messagesContainer);
            return;
        }

        confirmedStart = startDate;
        confirmedEnd = endDate;

        // Загружаем данные с новыми подтверждёнными датами
        load(confirmedStart, confirmedEnd);
    });

    // ---------- Сбросить на умолчания ----------
    resetBtn.addEventListener('click', () => {
        startInput.value = defaultStart;
        endInput.value = defaultEnd;
        confirmedStart = defaultStart;
        confirmedEnd = defaultEnd || null;

        messagesContainer.querySelectorAll('.message').forEach(msg => msg.remove());
        lastErrorMessage = null;

        load(confirmedStart, confirmedEnd);
    });

    // ---------- Автообновление (polling) ----------
    pollingInterval = setInterval(() => {
        load(confirmedStart, confirmedEnd);
    }, interval);

    return pollingInterval;
}
