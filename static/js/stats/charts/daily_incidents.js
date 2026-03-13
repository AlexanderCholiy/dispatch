import { getChartColors, getChartFonts, getChartRadius } from '../theme_colors.js';

export function createDailyIncidentsChart(ctx, initialData) {
    const colors = getChartColors();
    const fonts = getChartFonts();
    const radius = getChartRadius();

    // создаём график
    const chart = new Chart(ctx, {
        type: 'line',
        data: initialData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: false,
                    text: 'Динамика инцидентов',
                    color: colors.color,
                    font: { size: fonts.sm, weight: '550' }
                },
                legend: {
                    position: 'bottom',
                    labels: { color: colors.add_color }
                },
                tooltip: {
                    mode: 'nearest',
                    intersect: true,
                    backgroundColor: colors.add_bg,
                    titleColor: colors.color,
                    bodyColor: colors.add_color,
                    borderColor: colors.extra,
                    borderWidth: 1,
                    cornerRadius: radius.xl,
                    padding: 8,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            const datasetLabel = context.dataset.label;
                            const value = context.parsed.y; // значение на этом X

                            // считаем сумму всех datasets на этом индексе X
                            const dataIndex = context.dataIndex;
                            const total = context.chart.data.datasets
                                .reduce((sum, ds) => sum + (ds.data[dataIndex] || 0), 0) / 2;

                            const percent = total ? +(value / total * 100).toFixed(1) : 0;

                            return `${datasetLabel}: ${value} (${percent}%)`;
                        }
                    }
                },
                zoom: {
                    zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                    pan: { enabled: true, mode: 'x' }
                }
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: true },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Дата',
                        color: colors.add_color,
                        font: { size: fonts.sm, weight: '500' }
                    },
                    ticks: { color: colors.add_color, font: { size: fonts.xs, weight: '500' } },
                    grid: { color: colors.extra }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Количество инцидентов',
                        color: colors.add_color,
                        font: { size: fonts.sm, weight: '500' }
                    },
                    ticks: { color: colors.add_color, font: { size: fonts.xs, weight: '500' }, stepSize: 1, precision: 0 },
                    beginAtZero: true,
                    grid: { color: colors.extra }
                }
            }
        }
    });

    return chart;
}

export function updateDailyIncidentsChartColors(chart, regionColors) {
    if (!chart || !chart.data || !chart.options) return;

    const colors = getChartColors();

    // если regionColors не передали, используем дефолтный набор
    const defaultColors = [
        colors.extra,
        colors.pink,
        colors.cyan,
        colors.blue,
        colors.red,
        colors.yellow,
        colors.brown,
        colors.gray,
        colors.magenta,
        colors.green,
    ];

    const colorsToUse = regionColors && regionColors.length ? regionColors : defaultColors;

    chart.data.datasets.forEach((ds, idx) => {
        const color = colorsToUse[idx % colorsToUse.length];
        ds.borderColor = color;
        ds.backgroundColor = color;
        ds.fill = false;
    });

    // обновляем tooltip и остальные элементы графика
    chart.options.plugins.tooltip.backgroundColor = colors.add_bg;
    chart.options.plugins.tooltip.titleColor = colors.color;
    chart.options.plugins.tooltip.bodyColor = colors.add_color;
    chart.options.plugins.tooltip.borderColor = colors.extra;

    chart.options.plugins.title.color = colors.color;
    chart.options.plugins.legend.labels.color = colors.add_color;

    chart.options.scales.x.title.color = colors.add_color;
    chart.options.scales.y.title.color = colors.add_color;
    chart.options.scales.x.ticks.color = colors.add_color;
    chart.options.scales.y.ticks.color = colors.add_color;

    chart.options.scales.x.grid.color = colors.extra;
    chart.options.scales.y.grid.color = colors.extra;

    chart.update();
}
