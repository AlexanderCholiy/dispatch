import { getFirstDayOfPreviousMonth, formatDate } from './charts_utils.js';
import { updateDailyChart, updateBarChart, updateSlaCharts } from './data/charts_updater.js'

let isFetching = false;

async function fetchStatistics(startDate) {
    const res = await fetch(`/api/v1/report/statistics/?start_date=${startDate}`);
    if (!res.ok) throw new Error('Statistics API error');
    return res.json();
}

/* ---------- POLLING ---------- */

export function startStatisticsPolling(
    dailyChart,
    closedChart,
    openChart,
    slaCharts,
    interval = 10_000
) {
    const startDate = formatDate(getFirstDayOfPreviousMonth());

    const load = async () => {
        if (isFetching) return;
        isFetching = true;

        try {
            const apiData = await fetchStatistics(startDate);

            // DAILY
            updateDailyChart(dailyChart, apiData);

            // CLOSED BAR
            updateBarChart(closedChart, apiData, [
                'total_closed_incidents',
                'closed_incidents_with_power_issue',
            ]);

            // OPEN BAR
            updateBarChart(openChart, apiData, [
                'total_open_incidents',
                'open_incidents_with_power_issue',
            ]);

            // SLA
            updateSlaCharts(slaCharts.avr, apiData, 'avr');
            updateSlaCharts(slaCharts.rvr, apiData, 'rvr');

        } catch (e) {
            console.error('Polling error:', e);
        } finally {
            isFetching = false;
        }
    };

    load();
    return setInterval(load, interval);
}
