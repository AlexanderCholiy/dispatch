import { getFirstDayOfPreviousMonth, formatDate, showMessage, validateDateRange } from './charts_utils.js';
import { updateDailyChart, updateBarChart, updateSlaCharts, updateSubtypesChart } from './data/charts_updater.js';
import { updateCopyButton, updateSlaCopyData } from './data/copy_chart_data.js';

let ws = null;
const lastMsgRef = { current: null };

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
        console.log("WS connected");
        sendParams(confirmedStart, confirmedEnd);
    };

    ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.error) return showMessage(data.error, 'error', messagesContainer, lastMsgRef);

            const apiData = data.period ?? data;
            updateCharts(apiData);
        } catch (err) {
            console.error("WS parse error", err);
        }
    };

    ws.onerror = e => console.error("WS error", e);
    ws.onclose = () => console.warn("WS closed");

    function sendParams(start, end) {
        const payload = { start_date: start };
        if (end) payload.end_date = end;
        console.log("SEND FILTER", payload);
        ws.send(JSON.stringify(payload));
    }

    /* ---------- UPDATE CHARTS + COPY DATA ---------- */
    function updateCharts(apiData) {
        const macroregionLabels = apiData.map(r => r.macroregion);

        // DAILY
        updateDailyChart(charts.daily, apiData);

        // CLOSED
        updateBarChart(charts.closed, apiData, [
            'total_closed_incidents',
            'closed_incidents_with_power_issue'
        ], macroregionLabels);

        // OPEN
        updateBarChart(charts.open, apiData, [
            'total_open_incidents',
            'open_incidents_with_power_issue'
        ], macroregionLabels);

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

        // SLA DONUTS
        updateSlaCharts(charts.sla.avr, apiData, 'avr');
        updateSlaCharts(charts.sla.rvr, apiData, 'rvr');
        updateSlaCharts(charts.sla.dgu, apiData, 'dgu');

        // SUBTYPES (Power Issues)
        if (charts.subtypes?.power) {
            updateSubtypesChart(
                charts.subtypes.power.chart,
                apiData,
                'Аварии по питанию',
                charts.subtypes.power.labels,
                macroregionLabels
            );
            updateCopyButton(
                'energy-subtypes-chart-card',
                charts.subtypes.power.chart,
                'Регион/Подкатегория аварии по питанию'
            );
        }

        // ===== COPY DATA =====
        updateCopyButton('daily-chart-card', charts.daily, 'Дата/Регион');
        updateCopyButton('closed-chart-card', charts.closed, 'Регион/Количество инцидентов');
        updateCopyButton('open-chart-card', charts.open, 'Регион/Количество инцидентов');
        updateCopyButton('types-chart-card', charts.types, 'Регион/Тип аварии');

        // SLA таблицы
        updateSlaCopyData('avr-sla-grid', apiData, 'avr');
        updateSlaCopyData('rvr-sla-grid', apiData, 'rvr');
        updateSlaCopyData('dgu-sla-grid', apiData, 'dgu');
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
