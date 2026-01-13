import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';

function formatDateDDMMYYYY(dateStr) {
    const [year, month] = dateStr.split('-');
    return `01.${month}.${year}`;
}

function initWsDashboard() {
    const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
    const socketUrl = protocol + location.host + '/ws/incidents/stats/';
    const socket = new WebSocket(socketUrl);

    let previousPayloadKey = null;

    // Экземпляры графиков
    const charts = {
        closed: null,
        open: null,
        slaAvr: [],
        slaRvr: []
    };

    socket.onopen = () => console.log('WebSocket dashboard connected');
    socket.onclose = () => console.log('WebSocket dashboard closed');
    socket.onerror = (e) => console.error('WebSocket error', e);

    socket.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            if (payload.error) return console.error('WS error:', payload.error);

            const periodStats = Array.isArray(payload.period) ? payload.period : [];
            const fromDate = payload.meta?.period?.from;
            const formattedDate = fromDate ? formatDateDDMMYYYY(fromDate) : '';

            // ключ для сравнения (только from и данные)
            const newPayloadKey = JSON.stringify({ from: fromDate, period: periodStats });
            if (newPayloadKey === previousPayloadKey) return;
            previousPayloadKey = newPayloadKey;

            const rootStyles = getComputedStyle(document.documentElement);

            // -----------------------------
            // Заголовок
            // -----------------------------
            const container = document.querySelector('.stats');
            let h3 = container.querySelector('.dashboard-group-title');
            if (!h3) {
                h3 = document.createElement('h3');
                h3.className = 'dashboard-group-title';
                container.prepend(h3);
            }
            h3.textContent = `Статистика по инцидентам с ${formattedDate}`;

            // -----------------------------
            // Бар-чарты
            // -----------------------------
            const closedCanvas = document.getElementById('all-closed-incidents-chart');
            const openCanvas = document.getElementById('all-open-incidents-chart');

            const closedDatasets = [
                {
                    label: 'Закрытые инциденты',
                    valueKey: 'total_closed_incidents',
                    color: rootStyles.getPropertyValue('--green-color').trim()
                },
                {
                    label: 'Без питания',
                    valueKey: 'closed_incidents_with_power_issue',
                    color: rootStyles.getPropertyValue('--red-color').trim()
                }
            ];

            const openDatasets = [
                {
                    label: 'Открытые инциденты',
                    valueKey: 'total_open_incidents',
                    color: rootStyles.getPropertyValue('--blue-color').trim()
                },
                {
                    label: 'Без питания',
                    valueKey: 'open_incidents_with_power_issue',
                    color: rootStyles.getPropertyValue('--red-color').trim()
                }
            ];

            // создаём чарты один раз, потом обновляем данные
            if (!charts.closed) {
                charts.closed = renderAllIncidentsChart(closedCanvas, periodStats, { datasets: closedDatasets });
            } else {
                charts.closed.data.labels = periodStats.map(i => i.macroregion);
                charts.closed.data.datasets.forEach((ds, idx) => {
                    ds.data = periodStats.map(i => i[closedDatasets[idx].valueKey] ?? 0);
                });
                charts.closed.update();
            }

            if (!charts.open) {
                charts.open = renderAllIncidentsChart(openCanvas, periodStats, { datasets: openDatasets });
            } else {
                charts.open.data.labels = periodStats.map(i => i.macroregion);
                charts.open.data.datasets.forEach((ds, idx) => {
                    ds.data = periodStats.map(i => i[openDatasets[idx].valueKey] ?? 0);
                });
                charts.open.update();
            }

            // -----------------------------
            // SLA
            // -----------------------------
            const avrContainer = document.getElementById('avr-sla-grid');
            const rvrContainer = document.getElementById('rvr-sla-grid');

            // полностью очищаем контейнеры
            avrContainer.innerHTML = '';
            rvrContainer.innerHTML = '';

            // создаём заголовки
            const avrTitle = document.createElement('h3');
            avrTitle.className = 'dashboard-group-title';
            avrTitle.textContent = `SLA АВР с ${formattedDate}`;
            avrContainer.appendChild(avrTitle);

            const rvrTitle = document.createElement('h3');
            rvrTitle.className = 'dashboard-group-title';
            rvrTitle.textContent = `SLA РВР с ${formattedDate}`;
            rvrContainer.appendChild(rvrTitle);

            // создаём сетки
            const avrGrid = document.createElement('div');
            avrGrid.className = 'sla-grid';
            avrContainer.appendChild(avrGrid);

            const rvrGrid = document.createElement('div');
            rvrGrid.className = 'sla-grid';
            rvrContainer.appendChild(rvrGrid);

            // уничтожаем старые чарты
            charts.slaAvr.forEach(c => c.destroy?.());
            charts.slaRvr.forEach(c => c.destroy?.());
            charts.slaAvr = [];
            charts.slaRvr = [];

            // создаём новые чарты
            periodStats.forEach(region => {
                const avrCard = document.createElement('div');
                avrCard.className = 'sla-card';
                avrCard.innerHTML = `<canvas></canvas>`;
                avrGrid.appendChild(avrCard);

                charts.slaAvr.push(renderSlaDonut(
                    avrCard.querySelector('canvas'),
                    region.macroregion,
                    [
                        region.sla_avr_expired_count,
                        region.sla_avr_closed_on_time_count,
                        region.sla_avr_less_than_hour_count,
                        region.sla_avr_in_progress_count
                    ]
                ));

                const rvrCard = document.createElement('div');
                rvrCard.className = 'sla-card';
                rvrCard.innerHTML = `<canvas></canvas>`;
                rvrGrid.appendChild(rvrCard);

                charts.slaRvr.push(renderSlaDonut(
                    rvrCard.querySelector('canvas'),
                    region.macroregion,
                    [
                        region.sla_rvr_expired_count,
                        region.sla_rvr_closed_on_time_count,
                        region.sla_rvr_less_than_hour_count,
                        region.sla_rvr_in_progress_count
                    ]
                ));
            });

        } catch (e) {
            console.error('Ошибка обработки WebSocket данных', e);
        }
    };
}

initWsDashboard();
