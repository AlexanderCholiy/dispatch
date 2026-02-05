import { getFirstDayOfPreviousMonth, formatDate, showMessage, validateDateRange } from './charts_utils.js';
import { updateDailyChart, updateBarChart, updateSlaCharts, updateSubtypesChart } from './data/charts_updater.js';
import { updateCopyButton, updateSlaCopyData } from './data/copy_chart_data.js'

let isFetching = false;
let pollingInterval = null;
const lastMsgRef = { current: null };

async function fetchStatistics(startDate, endDate = null) {
    let url = `/api/v1/report/statistics/?start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error('Statistics API error');
    return res.json();
}

function updateCharts(apiData, dailyChart, closedChart, openChart, typesChart, slaCharts, subtypesCharts = {}) {
    // Список макрорегионов из API
    const macroregionLabels = apiData.map(r => r.macroregion);

    updateDailyChart(dailyChart, apiData);

    updateBarChart(closedChart, apiData, ['total_closed_incidents', 'closed_incidents_with_power_issue'], macroregionLabels);
    updateBarChart(openChart, apiData, ['total_open_incidents', 'open_incidents_with_power_issue'], macroregionLabels);

    updateSlaCharts(slaCharts.avr, apiData, 'avr');
    updateSlaCharts(slaCharts.rvr, apiData, 'rvr');
    updateSlaCharts(slaCharts.dgu, apiData, 'dgu');

    updateBarChart(typesChart, apiData, [
        'is_power_issue_type',
        'is_ams_issue_type',
        'is_goverment_request_issue_type',
        'is_vols_issue_type',
        'is_object_destruction_issue_type',
        'is_object_access_issue_type',
    ], macroregionLabels);

    // ===== ОБНОВЛЕНИЕ ПОДТИПОВ =====
    if (subtypesCharts.power) {
        updateSubtypesChart(
            subtypesCharts.power.chart,
            apiData,
            'Аварии по питанию',
            subtypesCharts.power.labels,
            macroregionLabels
        );
    }

    // ===== ОБНОВЛЕНИЕ COPY DATA =====
    updateCopyButton('daily-chart-card', dailyChart, 'Дата/Регион');
    updateCopyButton('closed-chart-card', closedChart, 'Регион/Количество инцидентов');
    updateCopyButton('open-chart-card', openChart, 'Регион/Количество инцидентов');
    updateCopyButton('types-chart-card', typesChart, 'Регион/Тип аварии');

    if (subtypesCharts.power) {
        updateCopyButton(
            'energy-subtypes-chart-card',
            subtypesCharts.power.chart,
            'Регион/Подкатегория аварии по питанию'
        );
    }

    // SLA таблицы
    updateSlaCopyData('avr-sla-grid', apiData, 'avr');
    updateSlaCopyData('rvr-sla-grid', apiData, 'rvr');
    updateSlaCopyData('dgu-sla-grid', apiData, 'dgu');
}

export function startStatisticsPolling(charts, interval = 10_000) {
    const { daily, closed, open, types, sla, subtypes } = charts;

    const startInput = document.getElementById('start-date');
    const endInput = document.getElementById('end-date');
    const applyBtn = document.getElementById('apply-period');
    const resetBtn = document.getElementById('reset-period');
    const messagesContainer = document.querySelector('.messages-container');

    const defaultStart = formatDate(getFirstDayOfPreviousMonth());
    const defaultEnd = '';
    startInput.value = defaultStart;
    endInput.value = defaultEnd;

    const today = new Date().toISOString().split('T')[0];
    endInput.max = today;

    let confirmedStart = defaultStart;
    let confirmedEnd = defaultEnd || null;

    async function load(startDate, endDate) {
        if (isFetching) return;
        isFetching = true;
        try {
            const apiData = await fetchStatistics(startDate, endDate);
            if (apiData.error) return showMessage(apiData.error, 'error', messagesContainer, lastMsgRef);

            updateCharts(apiData, daily, closed, open, types, sla, subtypes);
        } catch (e) {
            console.error('Polling error:', e);
            showMessage('Ошибка при получении статистики', 'error', messagesContainer, lastMsgRef);
        } finally {
            isFetching = false;
        }
    }

    load(confirmedStart, confirmedEnd);

    applyBtn.addEventListener('click', () => {
        const startDate = startInput.value;
        const endDate = endInput.value || null;

        if (!validateDateRange(startDate, endDate)) {
            return showMessage('Дата начала не может быть больше даты конца', 'warning', messagesContainer, lastMsgRef);
        }

        confirmedStart = startDate;
        confirmedEnd = endDate;
        load(confirmedStart, confirmedEnd);
    });

    resetBtn.addEventListener('click', () => {
        startInput.value = defaultStart;
        endInput.value = defaultEnd;
        confirmedStart = defaultStart;
        confirmedEnd = defaultEnd || null;

        messagesContainer.querySelectorAll('.message').forEach(msg => msg.remove());
        lastMsgRef.current = null;

        load(confirmedStart, confirmedEnd);
    });

    pollingInterval = setInterval(() => load(confirmedStart, confirmedEnd), interval);
    return pollingInterval;
}
