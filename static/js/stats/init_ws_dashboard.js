import { renderAllIncidentsChart } from './charts/all_incidents_chart.js';
import { renderSlaDonut } from './charts/sla_chart.js';

function formatDateDDMMYYYY(dateStr) {
    const [year, month, day] = dateStr.split('-');
    return `01.${month}.${year}`;
}

function initWsDashboard() {
    const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
    const socketUrl = protocol + location.host + '/ws/incidents/stats/';
    const socket = new WebSocket(socketUrl);

    // Кеш предыдущих данных
    let previousData = {
        all_period: null,
        current_month: null
    };

    socket.onopen = () => console.log('WebSocket connected');
    socket.onclose = () => console.log('WebSocket closed');
    socket.onerror = (e) => console.error('WebSocket error', e);

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.error) {
                console.error('Error from server:', data.error);
                return;
            }

            // Сравниваем данные, если не изменились — не обновляем графики
            const allPeriodStr = JSON.stringify(data.all_period);
            const currentMonthStr = JSON.stringify(data.current_month);

            if (
                allPeriodStr === previousData.all_period &&
                currentMonthStr === previousData.current_month
            ) {
                return; // Данные не изменились
            }

            // Сохраняем новые данные
            previousData.all_period = allPeriodStr;
            previousData.current_month = currentMonthStr;

            const rootStyles = getComputedStyle(document.documentElement);
            const periodStart = data.meta.period.from;
            const formattedDate = formatDateDDMMYYYY(periodStart);

            // -----------------------------
            // Графики "Все инциденты" и "С текущего месяца"
            // -----------------------------
            renderAllIncidentsChart(
                document.getElementById('all-incidents-chart'),
                data.all_period,
                {
                    title: 'Инциденты за всё время',
                    label: 'Всего инцидентов',
                    valueKey: 'total_incidents',
                    color: rootStyles.getPropertyValue('--blue-color').trim() || '#3b82f6'
                }
            );

            renderAllIncidentsChart(
                document.getElementById('all-incidents-chart-period'),
                data.current_month,
                {
                    title: `Инциденты с ${formattedDate}`,
                    label: `Открытые инциденты с ${formattedDate}`,
                    valueKey: 'total_open_incidents',
                    color: rootStyles.getPropertyValue('--red-color').trim() || '#c02f1cff'
                }
            );

            // -----------------------------
            // SLA Сетки
            // -----------------------------
            const avrGridContainer = document.getElementById('avr-sla-grid');
            const rvrGridContainer = document.getElementById('rvr-sla-grid');

            avrGridContainer.innerHTML = '';
            rvrGridContainer.innerHTML = '';

            const avrTitle = document.createElement('h3');
            avrTitle.className = 'dashboard-group-title';
            avrTitle.textContent = `SLA АВР с ${formattedDate}`;
            avrGridContainer.appendChild(avrTitle);

            const rvrTitle = document.createElement('h3');
            rvrTitle.className = 'dashboard-group-title';
            rvrTitle.textContent = `SLA РВР с ${formattedDate}`;
            rvrGridContainer.appendChild(rvrTitle);

            const avrGrid = document.createElement('div');
            avrGrid.className = 'sla-grid';
            avrGridContainer.appendChild(avrGrid);

            const rvrGrid = document.createElement('div');
            rvrGrid.className = 'sla-grid';
            rvrGridContainer.appendChild(rvrGrid);

            data.current_month.forEach(region => {
                const avrCard = document.createElement('div');
                avrCard.className = 'sla-card';
                avrCard.innerHTML = `<canvas></canvas>`;
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

                const rvrCard = document.createElement('div');
                rvrCard.className = 'sla-card';
                rvrCard.innerHTML = `<canvas></canvas>`;
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

initWsDashboard();
