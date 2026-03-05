/**
 * Обновляет текст элемента и класс empty
 */
function updateElementValue(el, value) {
    const val = value ?? 0;

    el.textContent = val;

    if (val === 0) {
        el.classList.add('empty');
    } else {
        el.classList.remove('empty');
    }
}


/**
 * Обновляет счетчики "Всего" для графиков.
 * @param {Chart} chart
 * @param {Array<{id: string, field?: string}>} targets
 */
export function updateTotalCount(chart, targets = [{ id: 'daily-total-count' }]) {
    if (!chart?.data?.datasets?.length) return;

    targets.forEach(({ id, field }) => {
        const el = document.getElementById(id);
        if (!el) return;

        let total = 0;

        if (field != null) {
            const ds =
                chart.data.datasets.find(d => d.label === field) ||
                chart.data.datasets[0];

            total = ds.data.reduce((sum, v) => sum + (v || 0), 0);

        } else {
            total = chart.data.datasets.reduce(
                (sum, ds) => sum + ds.data.reduce((a, b) => a + (b || 0), 0),
                0
            );
        }

        updateElementValue(el, total);
    });
}


/**
 * Обновляет SLA счетчики из нескольких графиков
 */
export function updateSlaTotalCounts(charts, targets) {
    if (!charts?.length) return;

    const totals = [0, 0, 0, 0];

    charts.forEach(chart => {
        if (!chart?.$hasData) return;

        const data = chart.data.datasets?.[0]?.data || [];

        data.forEach((value, idx) => {
            totals[idx] += value || 0;
        });
    });

    targets.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (!el) return;

        updateElementValue(el, totals[idx]);
    });
}

/**
 * Обновляет суммы категорий/подкатегорий графика
 * @param {Chart} chart
 * @param {Array<{id: string, label: string}>} targets
 */
export function updateCategoryTotals(chart, targets) {
    if (!chart?.data?.datasets?.length) return;

    targets.forEach(({ id, index }) => {
        const el = document.getElementById(id);
        if (!el) return;

        const dataset = chart.data.datasets[index];
        if (!dataset) return;

        const total = dataset.data.reduce((sum, v) => sum + (v || 0), 0);

        updateElementValue(el, total);
    });
}

/**
 * Обновляет суммы нескольких датасетов графика по индексам и отображает их в элементах
 * @param {Chart} chart - Chart.js объект
 * @param {Array<{id: string, indexes: number[]}>} targets - массив целей с id элемента и индексами датасетов
 */
export function updateChartTotals(chart, targets = []) {
    if (!chart?.data?.datasets?.length) return;

    targets.forEach(({ id, indexes }) => {
        const el = document.getElementById(id);
        if (!el) return;

        let total = 0;

        indexes.forEach(i => {
            const dataset = chart.data.datasets[i];
            if (!dataset?.data?.length) return;

            total += dataset.data.reduce((sum, v) => sum + (v || 0), 0);
        });

        updateElementValue(el, total);
    });
}