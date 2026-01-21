import { updateDailyChart, updateBarChart, updateSlaCharts } from './data/charts_updater.js';

export function startStatisticsWebSocket(dashboardCharts) {
    if (!window.WebSocket) return console.error('WebSocket not supported');

    const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${wsScheme}://${window.location.host}/ws/incidents/stats/`;

    let socket;
    let reconnectTimeout = 10000; // 10 секунд перед новой попыткой

    const connect = () => {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('WS connected');
        };

        socket.onclose = (e) => {
            console.warn('WS disconnected, retrying in 10s', e);
            setTimeout(connect, reconnectTimeout);
        };

        socket.onerror = (err) => {
            console.error('WS error:', err);
            // закрываем соединение чтобы запустился onclose и попытка reconnect
            socket.close();
        };

        socket.onmessage = (event) => {
            let data;
            try {
                data = JSON.parse(event.data);
            } catch (e) {
                console.error('WS parse error:', e);
                return;
            }

            if (data.error) {
                console.error('WS error:', data.error);
                return;
            }

            try {
                const stats = data.period;

                // daily
                updateDailyChart(dashboardCharts.daily, stats);

                // closed
                updateBarChart(dashboardCharts.closed, stats, [
                    'total_closed_incidents',
                    'closed_incidents_with_power_issue'
                ]);

                // open
                updateBarChart(dashboardCharts.open, stats, [
                    'total_open_incidents',
                    'open_incidents_with_power_issue'
                ]);

                // SLA
                updateSlaCharts(dashboardCharts.sla.avr, stats, 'avr');
                updateSlaCharts(dashboardCharts.sla.rvr, stats, 'rvr');

            } catch (e) {
                console.error('WS update error:', e);
                // данные не обновляются, но старые остаются видимыми
            }
        };
    };

    connect();

    return {
        close: () => socket?.close(),
    };
}
