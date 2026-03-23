import { getFirstDayOfPreviousMonth, formatDate, showMessage, validateDateRange } from './charts_utils.js';
import { updateDailyChart, updateBarChart, updateSlaCharts, updateSubtypesChart } from './data/charts_updater.js';
import { updateCopyButton, updateSlaCopyData } from './data/copy_chart_data.js';
import { updateTotalCount, updateSlaTotalCounts, updateCategoryTotals, updateChartTotals } from './data/update_total_counter.js'
import { updateHourlyGrid } from './data/hourly_grid_updater.js';
import { initWeeklyMacroregionsTable, updateWeeklyMacroregionsTable } from './data/weekly_macroregions_table.js';
import { initAvrContractorsTable, updateAvrContractorsTable } from './data/avr_contractors_table.js';
import { updateDispatchSlaTables } from './data/dispatch_sla_table.js'; // ✅ ДОБАВИЛИ

let ws = null;
const lastMsgRef = { current: null };

let lastWeeklyStart = null;
let lastWeeklyEnd = null;

let lastAvrStart = null;
let lastAvrEnd = null;


export function startStatisticsWebSocket(charts) {
    const startInput = document.getElementById('start-date');
    const endInput = document.getElementById('end-date');
    const applyBtn = document.getElementById('apply-period');
    const resetBtn = document.getElementById('reset-period');
    const messagesContainer = document.querySelector('.messages-container');

    const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${wsScheme}://${window.location.host}/ws/incidents/stats/`;

    const defaultStart = formatDate(getFirstDayOfPreviousMonth());
    const defaultEnd = '';

    startInput.value = defaultStart;
    endInput.value = defaultEnd;
    endInput.max = new Date().toISOString().split('T')[0];

    let confirmedStart = defaultStart;
    let confirmedEnd = null;

    /* ---------- CONNECT ---------- */
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        sendParams(confirmedStart, confirmedEnd);
    };

    ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);

            if (data.error) {
                return showMessage(data.error, 'error', messagesContainer, lastMsgRef);
            }

            // ✅ ВАЖНО: правильно достаём все уровни
            const apiData = data.period ?? data;
            const avrData = data.avr_period ?? null;
            const dispatchData = data.dispatch_data ?? null;

            updateCharts(apiData, avrData, dispatchData);

        } catch (err) {
            console.error("WS parse error", err);
        }
    };

    ws.onerror = e => console.error("WS error", e);
    ws.onclose = () => console.warn("WS closed");

    function sendParams(start, end) {
        const payload = { start_date: start };
        if (end) payload.end_date = end;
        ws.send(JSON.stringify(payload));
    }

    /* ---------- UPDATE CHARTS + COPY DATA ---------- */
    function updateCharts(apiData, avrData = null, dispatchData = null) {
        const macroregionLabels = apiData.map(r => r.macroregion);

        // DAILY
        updateDailyChart(charts.daily, apiData);
        updateTotalCount(charts.daily, [
            { id: 'daily-total-count' }
        ]);

        if (apiData.length > 0) {
            updateHourlyGrid(apiData[0], 'hours-total-grid');
        }

        // WEEKLY TABLE
        const startDate = confirmedStart;
        const endDate = confirmedEnd || new Date().toISOString().split('T')[0];

        const needRebuildWeekly =
            startDate !== lastWeeklyStart ||
            endDate !== lastWeeklyEnd;

        if (needRebuildWeekly) {
            initWeeklyMacroregionsTable(
                'weekly-incidents-table',
                apiData,
                startDate,
                endDate
            );

            lastWeeklyStart = startDate;
            lastWeeklyEnd = endDate;
        } else {
            updateWeeklyMacroregionsTable(apiData);
        }

        // AVR CONTRACTORS TABLE
        const avrTableContainer = document.getElementById('avr-contractors-table');

        if (avrTableContainer && avrData) {
            const needRebuildAvr =
                startDate !== lastAvrStart ||
                endDate !== lastAvrEnd;

            if (avrData.error) {
                console.warn('AVR data error:', avrData.error);
                showMessage('Ошибка загрузки данных по подрядчикам', 'warning', messagesContainer, lastMsgRef);
                return;
            }

            if (needRebuildAvr) {
                initAvrContractorsTable(
                    avrTableContainer,
                    avrData,
                    startDate,
                    endDate
                );

                lastAvrStart = startDate;
                lastAvrEnd = endDate;
            } else {
                updateAvrContractorsTable(avrData);
            }
        }

        // CLOSED
        updateBarChart(charts.closed, apiData, [
            'total_closed_incidents',
            'closed_incidents_with_power_issue'
        ], macroregionLabels);

        updateTotalCount(charts.closed, [
            { id: 'closed-total-count', field: 'Всего' },
            { id: 'closed-energy-total-count', field: 'Без питания' }
        ]);

        // OPEN
        updateBarChart(charts.open, apiData, [
            'total_open_incidents',
            'open_incidents_with_power_issue'
        ], macroregionLabels);

        updateTotalCount(charts.open, [
            { id: 'open-total-count', field: 'Всего' },
            { id: 'open-energy-total-count', field: 'Без питания' }
        ]);

        // SLA DONUTS
        updateSlaCharts(charts.sla.avr, apiData, 'avr');
        updateSlaTotalCounts(charts.sla.avr, [
            'avr-expired-total',
            'avr-on-time-total',
            'avr-less-hour-total',
            'avr-in-work-total',
        ]);

        updateSlaCharts(charts.sla.rvr, apiData, 'rvr');
        updateSlaTotalCounts(charts.sla.rvr, [
            'rvr-expired-total',
            'rvr-on-time-total',
            'rvr-less-hour-total',
            'rvr-in-work-total',
        ]);

        updateSlaCharts(charts.sla.dgu, apiData, 'dgu');
        updateSlaTotalCounts(charts.sla.dgu, [
            'dgu-expired-total',
            'dgu-on-time-total',
            'dgu-less-hour-total',
            'dgu-in-work-total',
        ]);

        // TYPES
        updateBarChart(
            charts.types,
            apiData,
            [
                'is_power_issue_type',
                'is_ams_issue_type',
                'is_goverment_request_issue_type',
                'is_vols_issue_type',
                'is_object_destruction_issue_type',
                'is_object_access_issue_type'
            ],
            macroregionLabels
        );

        updateCategoryTotals(charts.types, [
            { id: 'total-power', index: 0 },
            { id: 'total-ams', index: 1 },
            { id: 'total-government', index: 2 },
            { id: 'total-vols', index: 3 },
            { id: 'total-destruction', index: 4 },
            { id: 'total-access', index: 5 },
        ]);

        updateChartTotals(charts.types, [
            { id: 'types-power-total', indexes: [0] },
            { id: 'types-other-total', indexes: [1,2,3,4,5] }
        ]);

        // SUBTYPES
        if (charts.subtypes?.power) {
            updateSubtypesChart(
                charts.subtypes.power.chart,
                apiData,
                'Аварии по питанию',
                charts.subtypes.power.labels,
                macroregionLabels
            );

            updateCategoryTotals(charts.subtypes.power.chart, [
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

            updateChartTotals(charts.subtypes.power.chart, [
                { id: 'power-no-subtype-total', indexes: [16] },
                { id: 'power-other-total', indexes: [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] }
            ]);

            updateCopyButton(
                'energy-subtypes-chart-card',
                charts.subtypes.power.chart,
                'Регион/Подкатегория аварии по питанию'
            );
        }

        // COPY
        updateCopyButton('daily-chart-card', charts.daily, 'Дата/Регион');
        updateCopyButton('closed-chart-card', charts.closed, 'Регион/Количество инцидентов');
        updateCopyButton('open-chart-card', charts.open, 'Регион/Количество инцидентов');
        updateCopyButton('types-chart-card', charts.types, 'Регион/Тип аварии');

        updateSlaCopyData('avr-sla-grid', apiData, 'avr');
        updateSlaCopyData('rvr-sla-grid', apiData, 'rvr');
        updateSlaCopyData('dgu-sla-grid', apiData, 'dgu');

        // ✅ DISPATCH SLA TABLES (FIX)
        if (dispatchData) {
            updateDispatchSlaTables(dispatchData);
        }
    }

    /* ---------- APPLY FILTER ---------- */
    applyBtn.addEventListener('click', () => {
        const start = startInput.value;
        const end = endInput.value || null;

        if (!validateDateRange(start, end)) {
            return showMessage('Дата начала больше даты конца', 'warning', messagesContainer, lastMsgRef);
        }

        confirmedStart = start;
        confirmedEnd = end;

        sendParams(confirmedStart, confirmedEnd);
    });

    /* ---------- RESET ---------- */
    resetBtn.addEventListener('click', () => {
        startInput.value = defaultStart;
        endInput.value = defaultEnd;

        confirmedStart = defaultStart;
        confirmedEnd = null;

        messagesContainer.querySelectorAll('.message').forEach(m => m.remove());
        lastMsgRef.current = null;

        sendParams(confirmedStart, confirmedEnd);
    });
}