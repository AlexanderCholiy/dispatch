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

    // Таблица
    const table = document.createElement('table');
    table.className = 'avr-contractors-table custom-table';
    containerEl.appendChild(table);

    // Заголовки
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    [
        'Подрядчик',
        'Макрорегион',
        'Просрочено',
        'Закрыто вовремя',
        'Менее часа',
        'В работе',
        'Всего (SLA)',
        'SLA, %'
    ].forEach(text => {
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

    let groupCounter = 0;

    tbody.querySelectorAll('tr').forEach(r => r.remove());

    data.forEach(contractor => {
        const rowsCount = contractor.macroregions.length;
        const groupId = `group-${groupCounter++}`;

        contractor.macroregions.forEach((region, index) => {
            const tr = document.createElement('tr');
            tr.dataset.groupId = groupId; // Уникальный id для группы

            // Подрядчик (только первая строка для rowspan)
            if (index === 0) {
                const tdName = document.createElement('td');
                tdName.textContent = contractor.contractor_name;
                tdName.rowSpan = rowsCount;
                tr.appendChild(tdName);
            }

            // Макрорегион
            const tdRegion = document.createElement('td');
            tdRegion.textContent = region.macroregion;
            tr.appendChild(tdRegion);

            // Функция для числовых ячеек с классом empty при 0
            const createNumericCell = (value) => {
                const td = document.createElement('td');
                td.textContent = value ?? 0;
                if (!value || value === 0) td.classList.add('empty');
                return td;
            };

            tr.appendChild(createNumericCell(region.sla_expired_count));
            tr.appendChild(createNumericCell(region.sla_closed_on_time_count));
            tr.appendChild(createNumericCell(region.sla_waiting_count));
            tr.appendChild(createNumericCell(region.sla_in_progress_count));

            // Всего (SLA) и SLA % — только для первой строки
            if (index === 0) {
                const tdTotal = createNumericCell(contractor.total_incidents_for_sla);
                tdTotal.rowSpan = rowsCount;
                tr.appendChild(tdTotal);

                const tdPercent = document.createElement('td');
                tdPercent.textContent = contractor.on_time_percentage != null
                    ? parseFloat(contractor.on_time_percentage.toFixed(1)) + '%'
                    : '0%';
                tdPercent.rowSpan = rowsCount;

                const percent = contractor.on_time_percentage ?? 0;
                if (percent < 50) tdPercent.classList.add('low');
                else if (percent < 75) tdPercent.classList.add('medium');
                else if (percent < 90) tdPercent.classList.add('high');
                else tdPercent.classList.add('excellent');

                tr.appendChild(tdPercent);
            }

            tbody.appendChild(tr);
        });
    });
}


export function maybeUpdateAvrContractorsTable(data, startDate, endDate) {
    if (startDate !== lastStart || endDate !== lastEnd) {
        initAvrContractorsTable('avr-contractors-table', data, startDate, endDate);
    } else {
        updateAvrContractorsTable(data);
    }
}