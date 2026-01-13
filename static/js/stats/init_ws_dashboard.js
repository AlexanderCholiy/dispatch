import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';

function formatDateDDMMYYYY(dateStr) {
    const [year, month] = dateStr.split('-');
    return `01.${month}.${year}`;
}

function clearContainer(id) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
}

export function initWsDashboard() {
    const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
    const socketUrl = `${protocol}${location.host}/ws/incidents/stats/`;
    const socket = new WebSocket(socketUrl);

    // кеш для защиты от лишних обновлений
    let previousPayloadHash = null;

    socket.onopen = () => {
        console.log('WebSocket dashboard connected');
    };

    socket.onclose = () => {
        console.log('WebSocket dashboard closed');
    };

    socket.onerror = (e) => {
        console.error('WebSocket error', e);
    };

    socket.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);

            if (payload.error) {
                console.error('WS error:', payload.error);
                return;
            }

            // 🔹 hash всего payload (дешево и надёжно)
            const currentHash = JSON.stringify(payload);
            if (currentHash === previousPayloadHash) return;
            previousPayloadHash = currentHash;

            const rootStyles = getComputedStyle(document.documentElement);

            const periodStart = payload.meta?.period?.from;
            const formattedDate = periodStart
                ? formatDateDDMMYYYY(periodStart)
                : '';

            // -----------------------------
            // Все инциденты
            // -----------------------------
            renderAllIncidentsChart(
                document.getElementById('all-incidents-chart'),
                payload.all_period,
                {
                    title: 'Инциденты за всё время',
                    label: 'Всего инцидентов',
                    valueKey: 'total_incidents',
                    color:
                        rootStyles.getPropertyValue('--blue-color').trim() ||
                        '#3b82f6'
                }
            );

            // -----------------------------
            // Инциденты за период
            // -----------------------------
            renderAllIncidentsChart(
                document.getElementById('all-incidents-chart-period'),
                payload.current_month,
                {
                    title: `Инциденты с ${formattedDate}`,
                    label: `Открытые инциденты с ${formattedDate}`,
                    valueKey: 'total_open_incidents',
                    color:
                        rootStyles.getPropertyValue('--red-color').trim() ||
                        '#ef4444'
                }
            );

            // -----------------------------
            // SLA
            // -----------------------------
            clearContainer('avr-sla-grid');
            clearContainer('rvr-sla-grid');

            const avrContainer = document.getElementById('avr-sla-grid');
            const rvrContainer = document.getElementById('rvr-sla-grid');

            const avrTitle = document.createElement('h3');
            avrTitle.className = 'dashboard-group-title';
            avrTitle.textContent = `SLA АВР с ${formattedDate}`;
            avrContainer.appendChild(avrTitle);

            const rvrTitle = document.createElement('h3');
            rvrTitle.className = 'dashboard-group-title';
            rvrTitle.textContent = `SLA РВР с ${formattedDate}`;
            rvrContainer.appendChild(rvrTitle);

            const avrGrid = document.createElement('div');
            avrGrid.className = 'sla-grid';
            avrContainer.appendChild(avrGrid);

            const rvrGrid = document.createElement('div');
            rvrGrid.className = 'sla-grid';
            rvrContainer.appendChild(rvrGrid);

            payload.current_month.forEach(region => {
                // АВР
                const avrCard = document.createElement('div');
                avrCard.className = 'sla-card';
                avrCard.innerHTML = '<canvas></canvas>';
                avrGrid.appendChild(avrCard);

                renderSlaDonut(
                    avrCard.querySelector('canvas'),
                    region.macroregion,
                    [
                        region.sla_avr_expired_count,
                        region.sla_avr_closed_on_time_count,
                        region.sla_avr_less_than_hour_count,
                        region.sla_avr_in_progress_count
                    ]
                );

                // РВР
                const rvrCard = document.createElement('div');
                rvrCard.className = 'sla-card';
                rvrCard.innerHTML = '<canvas></canvas>';
                rvrGrid.appendChild(rvrCard);

                renderSlaDonut(
                    rvrCard.querySelector('canvas'),
                    region.macroregion,
                    [
                        region.sla_rvr_expired_count,
                        region.sla_rvr_closed_on_time_count,
                        region.sla_rvr_less_than_hour_count,
                        region.sla_rvr_in_progress_count
                    ]
                );
            });

        } catch (e) {
            console.error('Ошибка обработки WebSocket данных', e);
        }
    };
}

// автостарт
initWsDashboard();
