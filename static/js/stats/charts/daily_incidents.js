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
                    display: true,
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
                            return `${context.dataset.label}: ${context.formattedValue}`;
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

export function updateDailyIncidentsChartColors(chart) {
    if (!chart || !chart.data || !chart.options) return;

    const colors = getChartColors();

    const regionColors = [
        colors.pink,
        colors.cyan,
        colors.blue,
        colors.red,
        colors.yellow,
        colors.brown,
        colors.gray,
        colors.magenta,
        colors.orange,
        colors.green,
    ];

    chart.data.datasets.forEach((ds, idx) => {
        const color = regionColors[idx % regionColors.length];

        ds.borderColor = color;
        ds.backgroundColor = color;
        ds.fill = false;
    });

    // обновляем tooltip
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
