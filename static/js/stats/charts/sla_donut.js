import { getChartColors, getChartFonts, getChartRadius } from '../theme_colors.js';
import { centerTextPlugin } from './plugins.js'

export function createSlaDonutChart(ctx, {
    title,
    single = true,
    data = [],
    datasetColors = [],
    total = 0,
}) {
    const colors = getChartColors();
    const fonts = getChartFonts();

    const hasData = data.length > 0 && total > 0;

    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: hasData ? data.map((_, i) => `Сегмент ${i+1}`) : ['Нет данных'],
            datasets: [{
                data: hasData ? data : [1],
                backgroundColor: hasData ? datasetColors : [colors.extra],
                borderWidth: single ? 0 : 1,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                datalabels: {
                    color: colors.bg,
                    font: { size: fonts.sm, weight: '550' },
                    formatter: (value, context) => {
                        const chart = context.chart;
                        const dataset = context.dataset;
                        const nonZeroCount = dataset.data.filter(v => v > 0).length;

                        // Показываем только если есть данные, значение > 0 и сегментов больше 1
                        return chart.$hasData && value > 0 && nonZeroCount > 1 ? value : '';
                    },
                    anchor: 'center',
                    align: 'center',
                },
                title: {
                    display: true,
                    text: title,
                    color: colors.color,
                    font: { size: fonts.sm, weight: '550' }
                },
                legend: { 
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: colors.add_color,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 15,
                        font: { size: fonts.xs }
                    }
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: colors.bg,
                    titleColor: colors.color,
                    bodyColor: colors.add_color,
                    borderColor: colors.extra,
                    borderWidth: 1,
                }
            }
        },
        plugins: [centerTextPlugin(), ChartDataLabels]
    });

    chart.$hasData = hasData;

    return chart;
}

export function updateSlaDonutChartColors(charts) {
    if (!Array.isArray(charts)) return;

    const colors = getChartColors();

    charts.forEach(chart => {
        if (!chart) return;

        const dataset = chart.data.datasets[0];

        // Если данных нет — принудительно серый
        if (!chart.$hasData) {
            dataset.backgroundColor = [colors.gray];
            dataset.borderColor = ['transparent'];
            dataset.borderWidth = 0;
        } else {
            // Границы всегда серые для нескольких сегментов
            const nonZeroCount = dataset.data.filter(v => v > 0).length;
            dataset.borderWidth = nonZeroCount > 1 ? 1 : 0;
            dataset.borderColor = dataset.data.map(v =>
                v > 0 && nonZeroCount > 1 ? colors.bg : 'transparent'
            );
        }

        // TITLE
        chart.options.plugins.title.color = colors.color;

        // TOOLTIP
        chart.options.plugins.tooltip.backgroundColor = colors.bg;
        chart.options.plugins.tooltip.titleColor = colors.color;
        chart.options.plugins.tooltip.bodyColor = colors.add_color;

        // Легенда
        chart.options.plugins.legend.labels.color = colors.add_color;

        // Datalabels
        if (chart.options.plugins.datalabels) {
            chart.options.plugins.datalabels.color = colors.bg;
        }

        chart.update();
    });
}