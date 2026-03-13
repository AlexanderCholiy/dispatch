/**
 * Обновляет текст элемента и класс empty
 */
function updateElementValue(el, value) {
    const val = Number(value) || 0;

    el.textContent = val;

    if (val === 0) {
        el.classList.add('empty');
    } else {
        el.classList.remove('empty');
    }
}


/**
 * Берёт сумму из первого dataset (Россия)
 */
function getRussiaDatasetTotal(chart, index = null) {
    const ds = chart?.data?.datasets?.[0];
    if (!ds?.data?.length) return 0;

    if (index !== null) {
        return Number(ds.data[index]) || 0;
    }

    return ds.data.reduce((sum, v) => sum + (Number(v) || 0), 0);
}


/**
 * Обновляет счетчики "Всего"
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

            total = (ds?.data || []).reduce((sum, v) => sum + (Number(v) || 0), 0);

        } else {
            total = chart.data.datasets.reduce(
                (sum, ds) =>
                    sum + (ds.data || []).reduce((a, b) => a + (Number(b) || 0), 0),
                0
            );
        }

        total = Math.round(total / 2);

        updateElementValue(el, total);
    });
}


/**
 * SLA счетчики (берём из России)
 */
export function updateSlaTotalCounts(charts, targets) {
    if (!charts?.length) return;

    const firstChart = charts.find(c => c?.data?.datasets?.length);
    if (!firstChart) return;

    targets.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (!el) return;

        const total = getRussiaDatasetTotal(firstChart, idx);

        updateElementValue(el, total);
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

        const total = Math.round(
            (dataset.data || []).reduce((sum, v) => sum + (Number(v) || 0), 0) / 2
        );

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

            total += dataset.data.reduce((sum, v) => sum + (Number(v) || 0), 0);
        });

        total = Math.round(total / 2);

        updateElementValue(el, total);
    });
}