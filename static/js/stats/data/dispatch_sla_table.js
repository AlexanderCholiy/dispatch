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
                    <th>Всего</th>
                    <th>SLA OK</th>
                    <th>SLA FAIL</th>
                    <th>% SLA</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    `;
}

/**
 * Обновление данных таблицы
 */
export function updateDispatchSlaTable(containerId, data, type) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const tbody = container.querySelector('tbody');
    if (!tbody) return;

    // очищаем только body (заголовки остаются)
    tbody.innerHTML = '';

    data.forEach(row => {
        const tr = document.createElement('tr');

        // определяем поля в зависимости от типа
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
            <td>${total}</td>
            <td class="text-success">${slaOk}</td>
            <td class="text-danger">${slaFail}</td>
            <td>${percent}%</td>
        `;

        tbody.appendChild(tr);
    });
}

/**
 * Общий метод (init + update)
 */
export function updateDispatchSlaTables(dispatchData) {
    if (!Array.isArray(dispatchData)) return;

    // сортировка (например по total убыванию)
    const sorted = [...dispatchData].sort((a, b) => b.total - a.total);

    // INIT (один раз)
    if (!isInitialized.open) {
        initDispatchSlaTable('open-dispatch-sla-table-container', 'open');
        isInitialized.open = true;
    }

    if (!isInitialized.closed) {
        initDispatchSlaTable('closed-dispatch-sla-table-container', 'closed');
        isInitialized.closed = true;
    }

    // UPDATE
    updateDispatchSlaTable('open-dispatch-sla-table-container', sorted, 'open');
    updateDispatchSlaTable('closed-dispatch-sla-table-container', sorted, 'closed');
}
