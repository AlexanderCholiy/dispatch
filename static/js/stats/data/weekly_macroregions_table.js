/* =====================================================
   WEEKLY MACROREGIONS TABLE (UTC FIX)
===================================================== */

let tableState = {
    weeks: [],
    regions: [],
    initialized: false
};

/* =====================================================
   HELPERS
===================================================== */

function toDate(d) {
    if (d instanceof Date) return d;
    return new Date(d); // если строка — преобразуем
}

function getUTCMonday(inputDate) {
    const date = toDate(inputDate);
    // создаём UTC дату
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const day = (d.getUTCDay() + 6) % 7; // ISO: 0 = Monday
    d.setUTCDate(d.getUTCDate() - day);
    d.setUTCHours(0, 0, 0, 0);
    return d;
}

function formatDate(date) {
    const y = date.getUTCFullYear();
    const m = String(date.getUTCMonth() + 1).padStart(2, '0');
    const d = String(date.getUTCDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

/* =====================================================
   BUILD WEEKS
===================================================== */

function buildWeeks(startDate, endDate) {
    const weeks = [];
    let current = getUTCMonday(startDate);
    const end = toDate(endDate);
    const endUTC = new Date(Date.UTC(end.getFullYear(), end.getMonth(), end.getDate()));

    while (current <= endUTC) {
        const weekStart = new Date(current);
        const weekEnd = new Date(current);
        weekEnd.setUTCDate(weekEnd.getUTCDate() + 6);
        if (weekEnd > endUTC) weekEnd.setTime(endUTC.getTime());

        weeks.push({
            key: `${formatDate(weekStart)}_${formatDate(weekEnd)}`,
            label: `${formatDate(weekStart)}<br>${formatDate(weekEnd)}`,
            start: weekStart,
            end: weekEnd
        });

        current.setUTCDate(current.getUTCDate() + 7);
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
    thFirst.textContent = 'Макрорегион / Неделя';
    trHead.appendChild(thFirst);

    weeks.forEach(w => {
        const th = document.createElement('th');
        th.innerHTML = w.label;
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
    if (prev === 0) return curr === 0 ? 0 : 100;
    return ((curr - prev) / prev) * 100;
}

function getDeltaClass(delta) {
    if (delta < 0) return 'delta-low';
    const abs = Math.abs(delta);
    if (abs < 10) return 'delta-low';
    if (abs < 30) return 'delta-medium';
    if (abs < 60) return 'delta-high';
    return 'delta-critical';
}

function getArrow(delta) {
    if (delta > 0) return '▲';
    if (delta < 0) return '▼';
    return '●';
}

/* =====================================================
   UPDATE TABLE
===================================================== */

export function updateWeeklyMacroregionsTable(apiData) {
    if (!tableState.initialized) return;

    const weekKeys = tableState.weeks.map(w => w.key);

    function getDateUTC(dateStr) {
        const d = new Date(dateStr);
        return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
    }

    // обновляем регионы
    apiData.slice(1).forEach(region => {
        const row = document.querySelector(`tr[data-region="${region.macroregion}"]`);
        if (!row) return;

        const weekTotals = [];

        tableState.weeks.forEach(week => {
            const weekStartUTC = Date.UTC(week.start.getUTCFullYear(), week.start.getUTCMonth(), week.start.getUTCDate());
            const weekEndUTC = Date.UTC(week.end.getUTCFullYear(), week.end.getUTCMonth(), week.end.getUTCDate());

            let count = 0;
            Object.entries(region.daily_incidents || {}).forEach(([dateStr, val]) => {
                const dUTC = getDateUTC(dateStr);
                if (dUTC >= weekStartUTC && dUTC <= weekEndUTC) count += val;
            });

            weekTotals.push(count);

            const cell = row.querySelector(`[data-week="${week.key}"]`);
            if (cell) {
                cell.textContent = count;
                cell.classList.toggle('empty', count === 0);
            }
        });

        // DELTA
        const prev = weekTotals[weekTotals.length - 2] || 0;
        const curr = weekTotals[weekTotals.length - 1] || 0;
        const delta = calcDelta(prev, curr);

        const deltaCell = row.querySelector(`[data-delta="${region.macroregion}"]`);
        if (deltaCell) {
            const arrow = getArrow(delta);
            const arrowClass = getDeltaClass(delta);
            deltaCell.innerHTML = `<span class="delta-arrow ${arrowClass}">${arrow}</span> ${Math.abs(delta).toFixed(0)}%`;
            deltaCell.className = '';
        }
    });

    // обновляем TOTAL row
    const totalData = apiData[0];
    const totalRow = document.querySelector('tr.total-row');
    if (!totalRow || !totalData) return;

    const weekTotals = [];

    tableState.weeks.forEach(week => {
        const weekStartUTC = Date.UTC(week.start.getUTCFullYear(), week.start.getUTCMonth(), week.start.getUTCDate());
        const weekEndUTC = Date.UTC(week.end.getUTCFullYear(), week.end.getUTCMonth(), week.end.getUTCDate());

        let count = 0;
        Object.entries(totalData.daily_incidents || {}).forEach(([dateStr, val]) => {
            const dUTC = getDateUTC(dateStr);
            if (dUTC >= weekStartUTC && dUTC <= weekEndUTC) count += val;
        });

        weekTotals.push(count);

        const cell = totalRow.querySelector(`[data-total-week="${week.key}"]`);
        if (cell) {
            cell.textContent = count;
            cell.classList.toggle('empty', count === 0);
        }
    });

    const prev = weekTotals[weekTotals.length - 2] || 0;
    const curr = weekTotals[weekTotals.length - 1] || 0;
    const delta = calcDelta(prev, curr);

    const deltaCell = totalRow.querySelector('[data-delta="total"]');
    if (deltaCell) {
        const arrow = getArrow(delta);
        const arrowClass = getDeltaClass(delta);
        deltaCell.innerHTML = `<span class="delta-arrow ${arrowClass}">${arrow}</span> ${Math.abs(delta).toFixed(0)}%`;
        deltaCell.className = '';
    }
}