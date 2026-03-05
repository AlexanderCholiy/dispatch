/**
 * Обновляет счетчики "Всего" для графиков.
 * @param {Chart} chart - экземпляр Chart.js
 * @param {Array<{id: string, field?: string}>} targets - массив объектов с ID span и необязательным полем, если нужно суммировать только конкретный датасет
 */
export function updateTotalCount(chart, targets = [{ id: 'daily-total-count' }]) {
    if (!chart || !chart.data.datasets?.length) return;

    targets.forEach(({ id, field }) => {
        const el = document.getElementById(id);
        if (!el) return;

        let total = 0;

        if (field != null) {
            // Считаем только указанный датасет
            const ds = chart.data.datasets.find(d => d.label === field) || chart.data.datasets[0];
            total = ds.data.reduce((sum, v) => sum + (v || 0), 0);
        } else {
            // Считаем все датасеты
            total = chart.data.datasets.reduce(
                (sum, ds) => sum + ds.data.reduce((a, b) => a + (b || 0), 0),
                0
            );
        }

        el.textContent = total;
    });
}