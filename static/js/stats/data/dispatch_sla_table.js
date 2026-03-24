// dispatch_sla_table.js

let isInitialized = {
    open: false,
    closed: false,
};

/**
 * Создание таблицы (один раз)
 */
export function initDispatchSlaTable(containerId, type) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
        <table class="dispatch-sla-table custom-table">
            <thead>
                <tr>
                    <th>Диспетчер</th>
                    <th>Всего заявок</th>
                    <th>В рамках SLA</th>
                    <th>Просрочено</th>
                    <th>SLA, %</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    `;
}

/**
 * Получить класс для числа
 */
function getValueClass(value) {
    return value === 0 ? 'empty' : '';
}

/**
 * Получить класс для SLA
 */
function getSlaClass(percent) {
    if (!percent || percent === 0) return 'empty';
    if (percent >= 90) return 'excellent';
    if (percent >= 70) return 'high';
    if (percent >= 50) return 'medium';
    return 'bad';
}

/**
 * Сортировка dispatch SLA
 */
function sortDispatchData(data, type) {
    return [...data].sort((a, b) => {
        let percentA, percentB;
        let totalA, totalB;

        if (type === 'open') {
            percentA = a.open_sla_percent ?? 0;
            percentB = b.open_sla_percent ?? 0;

            totalA = a.open_incidents ?? 0;
            totalB = b.open_incidents ?? 0;
        } else {
            percentA = a.closed_sla_percent ?? 0;
            percentB = b.closed_sla_percent ?? 0;

            totalA = a.closed_incidents ?? 0;
            totalB = b.closed_incidents ?? 0;
        }

        // 1. SLA (меньше = хуже → вверх)
        if (percentA !== percentB) {
            return percentA - percentB;
        }

        // 2. Кол-во (больше = выше)
        if (totalA !== totalB) {
            return totalB - totalA;
        }

        // 3. ID (меньше = выше)
        const idA = a.responsible_user_id ?? 999999;
        const idB = b.responsible_user_id ?? 999999;

        return idA - idB;
    });
}

/**
 * Обновление данных таблицы
 */
export function updateDispatchSlaTable(containerId, data, type) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const tbody = container.querySelector('tbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    data.forEach(row => {
        const tr = document.createElement('tr');

        let total, slaOk, slaFail, percent;

        if (type === 'open') {
            total = row.open_incidents;
            slaOk = row.open_sla_ok;
            slaFail = row.open_sla_failed;
            percent = row.open_sla_percent;
        } else {
            total = row.closed_incidents;
            slaOk = row.closed_sla_ok;
            slaFail = row.closed_sla_failed;
            percent = row.closed_sla_percent;
        }

        tr.innerHTML = `
            <td>${row.responsible_user_name || 'Отсутствует'}</td>
            
            <td class="${getValueClass(total)}">
                ${total}
            </td>
            
            <td class="${getValueClass(slaOk)}">
                ${slaOk}
            </td>
            
            <td class="${getValueClass(slaFail)}">
                ${slaFail}
            </td>
            
            <td class="${getSlaClass(percent)}">
                ${percent}%
            </td>
        `;

        tbody.appendChild(tr);
    });
}

/**
 * Общий метод (init + update)
 */
export function updateDispatchSlaTables(dispatchData) {
    if (!Array.isArray(dispatchData)) return;

    const openSorted = sortDispatchData(dispatchData, 'open');
    const closedSorted = sortDispatchData(dispatchData, 'closed');

    if (!isInitialized.open) {
        initDispatchSlaTable('open-dispatch-sla-table-container', 'open');
        isInitialized.open = true;
    }

    if (!isInitialized.closed) {
        initDispatchSlaTable('closed-dispatch-sla-table-container', 'closed');
        isInitialized.closed = true;
    }

    updateDispatchSlaTable(
        'open-dispatch-sla-table-container',
        openSorted,
        'open'
    );

    updateDispatchSlaTable(
        'closed-dispatch-sla-table-container',
        closedSorted,
        'closed'
    );
}