/* =====================================================
   WEEKLY MACROREGIONS TABLE
===================================================== */

let tableState = {
    weeks: [],
    regions: [],
    initialized: false
};


/* =====================================================
   HELPERS
===================================================== */

function getMonday(date) {

    const d = new Date(date);

    // ISO день недели (0 = Monday)
    const day = (d.getDay() + 6) % 7;

    d.setDate(d.getDate() - day);
    d.setHours(0, 0, 0, 0);

    return d;
}

function formatDate(date) {

    // const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');

    return `${m}-${d}`;
}


/* =====================================================
   BUILD WEEKS
===================================================== */

function buildWeeks(startDate, endDate) {
    const weeks = [];
    let current = getMonday(startDate);
    const end = new Date(endDate);

    while (current <= end) {
        const weekStart = new Date(current);
        const weekEnd = new Date(current);
        weekEnd.setDate(current.getDate() + 6);

        if (weekEnd > end) {
            weekEnd.setTime(end.getTime());
        }

        weeks.push({
            key: `${formatDate(weekStart)}_${formatDate(weekEnd)}`,
            label: `${formatDate(weekStart)}<br>${formatDate(weekEnd)}`, // перенос через <br>
            start: weekStart,
            end: weekEnd
        });

        current = new Date(current);
        current.setDate(current.getDate() + 7);
    }

    return weeks;
}

/* =====================================================
   INIT TABLE
===================================================== */

export function initWeeklyMacroregionsTable(containerId, apiData = null, startDate, endDate) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const weeks = buildWeeks(startDate, endDate);

    let regions = [];
    if (apiData && apiData.length) {
        regions = apiData.slice(1).map(r => r.macroregion);
    } else {
        regions = [
            'МР-1', 'МР-2', 'МР-3', 'МР-4',
            'МР-5', 'МР-6', 'МР-7', 'МР-8', 'МР-9'
        ];
    }

    tableState.weeks = weeks;
    tableState.regions = regions;
    tableState.initialized = true;

    const table = document.createElement('table');
    table.className = 'stats-table custom-table';

    const thead = document.createElement('thead');
    const trHead = document.createElement('tr');

    const thFirst = document.createElement('th');
    thFirst.textContent = 'Макрорегион';
    trHead.appendChild(thFirst);

    weeks.forEach(w => {
        const th = document.createElement('th');
        th.innerHTML = w.label; // важно — innerHTML чтобы <br> работал
        trHead.appendChild(th);
    });

    const thDelta = document.createElement('th');
    thDelta.textContent = 'w2w, %';
    trHead.appendChild(thDelta);

    thead.appendChild(trHead);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');

    regions.forEach(region => {
        const tr = document.createElement('tr');
        tr.dataset.region = region;

        const tdName = document.createElement('td');
        tdName.textContent = region;
        tr.appendChild(tdName);

        weeks.forEach(w => {
            const td = document.createElement('td');
            td.dataset.week = w.key;
            td.textContent = '0';
            td.classList.add('empty');
            tr.appendChild(td);
        });

        const tdDelta = document.createElement('td');
        tdDelta.dataset.delta = region;
        tdDelta.textContent = '0%';
        tr.appendChild(tdDelta);

        tbody.appendChild(tr);
    });

    // TOTAL row
    const trTotal = document.createElement('tr');
    trTotal.className = 'total-row';

    const tdTotalName = document.createElement('td');
    tdTotalName.textContent = 'Итого:';
    trTotal.appendChild(tdTotalName);

    weeks.forEach(w => {
        const td = document.createElement('td');
        td.dataset.totalWeek = w.key;
        td.textContent = '0';
        td.classList.add('empty');
        trTotal.appendChild(td);
    });

    const tdTotalDelta = document.createElement('td');
    tdTotalDelta.dataset.delta = 'total';
    tdTotalDelta.textContent = '0%';
    trTotal.appendChild(tdTotalDelta);

    tbody.appendChild(trTotal);

    table.appendChild(tbody);

    container.innerHTML = '';
    container.appendChild(table);
}


/* =====================================================
   DELTA HELPERS
===================================================== */

function calcDelta(prev, curr) {
    if (prev === 0) {
        if (curr === 0) return 0;
        return 100;
    }
    return ((curr - prev) / prev) * 100;
}

function getDeltaClass(delta) {
    // если дельта отрицательная — всегда хорошо
    if (delta < 0) return 'delta-low';

    const abs = Math.abs(delta);
    if (abs < 10) return 'delta-low';
    if (abs < 30) return 'delta-medium';
    if (abs < 60) return 'delta-high';
    return 'delta-critical';
}

function getArrow(delta) {
    if (delta > 0) return '▲';    // рост
    if (delta < 0) return '▼';    // падение
    return '●';                    // стабильно
}


/* =====================================================
   UPDATE TABLE
===================================================== */

export function updateWeeklyMacroregionsTable(apiData) {
    if (!tableState.initialized) return;

    const weekKeys = tableState.weeks.map(w => w.key);

    apiData.slice(1).forEach(region => {
        const row = document.querySelector(`tr[data-region="${region.macroregion}"]`);
        if (!row) return;

        const weekTotals = [];

        tableState.weeks.forEach(week => {
            let count = 0;
            Object.entries(region.daily_incidents || {}).forEach(([date, val]) => {
                const d = new Date(date);
                if (d >= week.start && d <= week.end) {
                    count += val;
                }
            });
            weekTotals.push(count);

            const cell = row.querySelector(`[data-week="${week.key}"]`);
            if (cell) {
                cell.textContent = count;
                if (count === 0) {
                    cell.classList.add('empty');
                } else {
                    cell.classList.remove('empty');
                }
            }
        });

        /* DELTA */
        const prev = weekTotals[weekTotals.length - 2] || 0;
        const curr = weekTotals[weekTotals.length - 1] || 0;
        const delta = calcDelta(prev, curr);

        const deltaCell = row.querySelector(`[data-delta="${region.macroregion}"]`);
        if (deltaCell) {
            const arrow = getArrow(delta);
            const arrowClass = getDeltaClass(delta);

            // стрелка в отдельном span
            deltaCell.innerHTML = `<span class="delta-arrow ${arrowClass}">${arrow}</span> ${Math.abs(delta).toFixed(0)}%`;

            // общий класс для ячейки оставляем только если нужен (можно очистить)
            deltaCell.className = '';
        }
    });
}