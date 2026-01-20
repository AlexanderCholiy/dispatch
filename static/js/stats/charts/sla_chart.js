import { getThemeVars } from './utils.js';

const centerTextPlugin = {
    id: 'centerText',
    afterDraw(chart) {
        const { ctx, chartArea } = chart;
        if (!chartArea) return;

        const x = (chartArea.left + chartArea.right) / 2;
        const y = (chartArea.top + chartArea.bottom) / 2;

        const opts = chart.options.plugins.centerText;
        if (!opts || !opts.text) return;

        ctx.save();
        ctx.fillStyle = opts.color;
        // Используем шрифт из настроек или дефолт
        ctx.font = opts.font || 'bold 16px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(opts.text, x, y);
        ctx.restore();
    }
};

export function renderSlaDonut(canvas, title, values = [0, 0, 0, 0]) {
    if (!canvas || !window.Chart) return;

    if (canvas._chartInstance) {
        canvas._chartInstance.destroy();
    }

    const theme = getThemeVars();
    const total = values.reduce((a, b) => a + b, 0);
    const isEmpty = total === 0;

    // Считаем количество ненулевых сегментов для красивых границ
    const nonZeroCount = values.filter(v => v > 0).length;
    const borderWidth = isEmpty || nonZeroCount === 1 ? 0 : 1;

    const data = {
        labels: ['Просрочено', 'Закрыто вовремя', 'Меньше часа', 'В работе'],
        datasets: [{
            data: isEmpty ? [1] : values,
            backgroundColor: isEmpty
                ? [theme.gridColor] // серый цвет для пустого графика
                : [theme.red, theme.green, theme.yellow, theme.blue],
            borderColor: theme.addBackground, // Цвет границы между сегментами
            borderWidth: borderWidth
        }]
    };

    const chart = new Chart(canvas, {
        type: 'doughnut',
        data,
        plugins: [centerTextPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                title: {
                    display: true,
                    text: title,
                    color: theme.titleColor,
                    font: { 
                        size: theme.fontSm,
                        weight: 'normal' 
                    },
                    padding: { bottom: 10 }
                },
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: theme.addTextColor,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 15,
                        font: { size: theme.fontXs }
                    }
                },
                tooltip: {
                    enabled: !isEmpty, // Отключаем тултип для пустых данных
                    backgroundColor: theme.addBackground,
                    titleColor: theme.textColor,
                    bodyColor: theme.addTextColor,
                    borderColor: theme.gridColor,
                    borderWidth: 1,
                },
                centerText: {
                    text: total.toString(),
                    color: theme.textColor,
                    font: `bold ${theme.fontMd}px sans-serif`
                }
            }
        },
    });

    // Реакция на смену темы (dark/light)
    const observer = new MutationObserver(() => {
        const t = getThemeVars();
        const dataset = chart.data.datasets[0];

        // Обновляем цвета сегментов
        dataset.backgroundColor = isEmpty
            ? [t.gridColor]
            : [t.red, t.green, t.yellow, t.blue];
        dataset.borderColor = t.addBackground;

        // Обновляем цвета шрифтов и элементов
        chart.options.plugins.legend.labels.color = t.addTextColor;
        chart.options.plugins.title.color = t.titleColor;
        
        // Обновляем тултипы
        chart.options.plugins.tooltip.backgroundColor = t.addBackground;
        chart.options.plugins.tooltip.titleColor = t.textColor;
        chart.options.plugins.tooltip.bodyColor = t.addTextColor;
        chart.options.plugins.tooltip.borderColor = t.gridColor;

        // Обновляем центральный текст
        if (chart.options.plugins.centerText) {
            chart.options.plugins.centerText.color = t.textColor;
        }

        chart.update();
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
    });

    canvas._chartInstance = chart;
    return chart;
}
