import { getFirstDayOfPreviousMonth, formatDate, showMessage, validateDateRange } from './charts_utils.js';
import { updateDailyChart, updateBarChart, updateSlaCharts } from './data/charts_updater.js';

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
            if (data.error) {
                return showMessage(data.error, 'error', messagesContainer, lastMsgRef);
            }
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

    function updateCharts(apiData) {
        updateDailyChart(charts.daily, apiData);
        updateBarChart(charts.closed, apiData, ['total_closed_incidents', 'closed_incidents_with_power_issue']);
        updateBarChart(charts.open, apiData, ['total_open_incidents', 'open_incidents_with_power_issue']);
        updateSlaCharts(charts.sla.avr, apiData, 'avr');
        updateSlaCharts(charts.sla.rvr, apiData, 'rvr');
    }

    /* ---------- APPLY ---------- */

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
