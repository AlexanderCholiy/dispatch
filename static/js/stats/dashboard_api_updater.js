import { getFirstDayOfPreviousMonth, formatDate, showMessage, validateDateRange } from './charts_utils.js';
import { updateDailyChart, updateBarChart, updateSlaCharts, updateSubtypesChart } from './data/charts_updater.js';
import { updateCopyButton, updateSlaCopyData } from './data/copy_chart_data.js'
import { updateTotalCount, updateSlaTotalCounts, updateCategoryTotals, updateChartTotals } from './data/update_total_counter.js'

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
    updateTotalCount(dailyChart, [
        { id: 'daily-total-count' }
    ]);

    updateBarChart(closedChart, apiData, ['total_closed_incidents', 'closed_incidents_with_power_issue'], macroregionLabels);
    updateTotalCount(closedChart, [
        { id: 'closed-total-count', field: 'Всего' },
        { id: 'closed-energy-total-count', field: 'Без питания' }
    ]);

    updateBarChart(openChart, apiData, ['total_open_incidents', 'open_incidents_with_power_issue'], macroregionLabels);
    updateTotalCount(openChart, [
        { id: 'open-total-count', field: 'Всего' },
        { id: 'open-energy-total-count', field: 'Без питания' }
    ]);

    updateSlaCharts(slaCharts.avr, apiData, 'avr');
    updateSlaTotalCounts(slaCharts.avr, [
        'avr-expired-total',
        'avr-on-time-total',
        'avr-less-hour-total',
        'avr-in-work-total',
    ]);
    updateSlaCharts(slaCharts.rvr, apiData, 'rvr');
    updateSlaTotalCounts(slaCharts.rvr, [
        'rvr-expired-total',
        'rvr-on-time-total',
        'rvr-less-hour-total',
        'rvr-in-work-total',
    ]);
    updateSlaCharts(slaCharts.dgu, apiData, 'dgu');
    updateSlaTotalCounts(slaCharts.dgu, [
        'dgu-expired-total',
        'dgu-on-time-total',
        'dgu-less-hour-total',
        'dgu-in-work-total',
    ]);

    updateBarChart(typesChart, apiData, [
        'is_power_issue_type',
        'is_ams_issue_type',
        'is_goverment_request_issue_type',
        'is_vols_issue_type',
        'is_object_destruction_issue_type',
        'is_object_access_issue_type',
    ], macroregionLabels);
    updateCategoryTotals(typesChart, [
        { id: 'total-power', index: 0 },
        { id: 'total-ams', index: 1 },
        { id: 'total-government', index: 2 },
        { id: 'total-vols', index: 3 },
        { id: 'total-destruction', index: 4 },
        { id: 'total-access', index: 5 },
    ]);
    updateChartTotals(typesChart, [
        { id: 'types-power-total', indexes: [0] },
        { id: 'types-other-total', indexes: [1,2,3,4,5] }
    ]);

    // ===== ОБНОВЛЕНИЕ ПОДТИПОВ =====
    if (subtypesCharts.power) {
        updateSubtypesChart(
            subtypesCharts.power.chart,
            apiData,
            'Аварии по питанию',
            subtypesCharts.power.labels,
            macroregionLabels
        );
        updateCategoryTotals(subtypesCharts.power.chart, [
            { id: 'eo-nb-vl-1kv', index: 0 },
            { id: 'eo-nb-vl-1kv-plus', index: 1 },
            { id: 'eo-nb-kl-1kv', index: 2 },
            { id: 'eo-nb-kl-1kv-plus', index: 3 },
            { id: 'eo-nb-ktp', index: 4 },
            { id: 'eo-nb-pu', index: 5 },
            { id: 'eo-nb-rsh', index: 6 },
            { id: 'eo-operator-line', index: 7 },
            { id: 'eo-operator-eu', index: 8 },
            { id: 'eo-so-emergency', index: 9 },
            { id: 'eo-so-planned', index: 10 },
            { id: 'eo-other', index: 11 },
            { id: 'eo-no-payment', index: 12 },
            { id: 'eo-self-recovery', index: 13 },
            { id: 'eo-shep', index: 14 },
            { id: 'eo-no-scheme', index: 15 },
            { id: 'eo-no-subtype', index: 16 },
        ]);
        updateChartTotals(subtypesCharts.power.chart, [
            { id: 'power-no-subtype-total', indexes: [16] },
            { id: 'power-other-total', indexes: [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] }
        ]);
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
