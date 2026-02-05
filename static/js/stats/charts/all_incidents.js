import { getChartColors, getChartFonts, getChartRadius } from '../theme_colors.js';

export function createAllIncidentsChart(ctx, initialData, label, horizontal = false) {
    const colors = getChartColors();
    const fonts = getChartFonts();
    const radius = getChartRadius();

    return new Chart(ctx, {
        type: 'bar',
        data: initialData,
        options: {
            indexAxis: horizontal ? 'y' : 'x',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                datalabels: {
                    color: colors.bg,
                    font: { size: fonts.sm, weight: '550' },
                    rotation: horizontal ? 0 : 270,
                    formatter: (value) => value === 0 ? '' : value, // скрываем нули
                },
                title: {
                    display: false,
                    text: label,
                    color: colors.color,
                    font: { size: fonts.sm, weight: '550' }
                },
                legend: {
                    position: 'bottom',
                    labels: { color: colors.add_color }
                },
                tooltip: {
                    backgroundColor: colors.add_bg,
                    titleColor: colors.color,
                    bodyColor: colors.add_color,
                    borderColor: colors.extra,
                    borderWidth: 1,
                    cornerRadius: radius.xl,
                    padding: 8,
                },
                zoom: {
                    zoom: {
                        wheel: { enabled: true },
                        pinch: { enabled: true },
                        mode: horizontal ? 'y' : 'x',
                        limits: {
                            x: { min: 0 },  // минимальное значение по x
                            y: { min: 0 }   // минимальное значение по y
                        }
                    },
                    pan: {
                        enabled: true,
                        mode: horizontal ? 'y' : 'x',
                        limits: {
                            x: { min: 0 },
                            y: { min: 0 }
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: horizontal ? 'Количество инцидентов' : 'Макрорегион',
                        color: colors.add_color,
                        font: { size: fonts.sm },
                    },
                    ticks: { color: colors.add_color, min: 0 },
                    grid: { color: colors.extra },
                    stacked: horizontal
                },
                y: {
                    title: {
                        display: true,
                        text: horizontal ? 'Макрорегион' : 'Количество инцидентов',
                        color: colors.add_color,
                        font: { size: fonts.sm }
                    },
                    ticks: { color: colors.add_color, precision: 0, min: 0 },
                    beginAtZero: true,
                    grid: { color: colors.extra },
                    stacked: horizontal
                }
            }
        },
        plugins: [ChartDataLabels]
    });
}

export function updateAllIncidentsChartColors(chart, datasetColors) {
    if (!chart) return;

    const colors = getChartColors();

    chart.data.datasets.forEach((ds, idx) => {
        ds.backgroundColor = datasetColors[idx];
        ds.borderColor = datasetColors[idx];
    });

    // TOOLTIP
    chart.options.plugins.tooltip.backgroundColor = colors.add_bg;
    chart.options.plugins.tooltip.titleColor = colors.color;
    chart.options.plugins.tooltip.bodyColor = colors.add_color;
    chart.options.plugins.tooltip.borderColor = colors.extra;

    // TITLE & LEGEND
    chart.options.plugins.title.color = colors.color;
    chart.options.plugins.legend.labels.color = colors.add_color;
    
    // SCALES
    chart.options.scales.x.title.color = colors.add_color;
    chart.options.scales.y.title.color = colors.add_color;
    chart.options.scales.x.ticks.color = colors.add_color;
    chart.options.scales.y.ticks.color = colors.add_color;
    chart.options.scales.x.grid.color = colors.extra;
    chart.options.scales.y.grid.color = colors.extra;

    // DATALABELS
    if (chart.options.plugins.datalabels) {
        chart.options.plugins.datalabels.color = colors.bg;
    }

    chart.update();
}
