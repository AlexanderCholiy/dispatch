let lastStart = null;
let lastEnd = null;

export function initAvrContractorsTable(container, data = null, startDate = null, endDate = null) {
    // Проверяем, что передан именно DOM элемент, а не строка ID
    let containerEl;
    if (typeof container === 'string') {
        containerEl = document.getElementById(container);
    } else {
        containerEl = container;
    }

    if (!containerEl) {
        console.error('initAvrContractorsTable: container not found', container);
        return;
    }

    // Удаляем старое содержимое
    containerEl.querySelectorAll(':scope > *').forEach(el => el.remove());

    // Заголовок таблицы
    const title = document.createElement('p');
    title.className = 'table-title';
    title.textContent = 'SLA АВР по подрядчикам';
    containerEl.appendChild(title);

    // Таблица
    const table = document.createElement('table');
    table.className = 'avr-contractors-table';
    containerEl.appendChild(table);

    // Заголовки
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    ['Подрядчик','Всего','В срок','Просрочено','<1ч','В работе'].forEach(text => {
        const th = document.createElement('th');
        th.textContent = text;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Тело таблицы
    const tbody = document.createElement('tbody');
    table.appendChild(tbody);

    // Если данные уже есть, заполняем
    if (data) {
        updateAvrContractorsTable(data, tbody);
    }

    lastStart = startDate;
    lastEnd = endDate;
}

export function updateAvrContractorsTable(data, tbody = null) {
    if (!data || !Array.isArray(data)) {
        console.warn('updateAvrContractorsTable: invalid data', data);
        return;
    }

    if (!tbody) {
        const table = document.querySelector('.avr-contractors-table');
        if (!table) return;
        tbody = table.querySelector('tbody');
    }

    if (!tbody) return;

    tbody.querySelectorAll('tr').forEach(r => r.remove());

    data.forEach(row => {
        if (!row.contractor_name) return;

        const tr = document.createElement('tr');

        const cells = [
            row.contractor_name,
            row.total_closed_incidents ?? 0,
            row.on_time_count ?? 0,
            row.expired_count ?? 0,
            row.less_hour_count ?? 0,
            row.in_work_count ?? 0
        ];

        cells.forEach(val => {
            const td = document.createElement('td');
            if (typeof val === 'number') {
                td.textContent = Number.isInteger(val) ? val : val.toFixed(1);
            } else {
                td.textContent = val;
            }
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });
}

export function maybeUpdateAvrContractorsTable(data, startDate, endDate) {
    if (startDate !== lastStart || endDate !== lastEnd) {
        initAvrContractorsTable('avr-contractors-table', data, startDate, endDate);
    } else {
        updateAvrContractorsTable(data);
    }
}