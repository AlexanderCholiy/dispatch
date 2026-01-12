function getThemeVars() {
    const s = getComputedStyle(document.documentElement);

    return {
        baseBg: s.getPropertyValue('--background-color').trim(),
        text: s.getPropertyValue('--add-color').trim(),
        bg: s.getPropertyValue('--add-background-color').trim(),
        grid: s.getPropertyValue('--extra-color').trim(),

        red: s.getPropertyValue('--red-color').trim(),
        green: s.getPropertyValue('--green-color').trim(),
        yellow: s.getPropertyValue('--yellow-color').trim(),
        blue: s.getPropertyValue('--blue-color').trim(),

        empty: s.getPropertyValue('--extra-color').trim()
    };
}

export function renderSlaDonut(canvas, title, values) {
    if (!canvas || !window.Chart) return;

    const theme = getThemeVars();
    const total = values.reduce((a, b) => a + b, 0);

    const isEmpty = total === 0;

    const data = {
        labels: isEmpty
            ? ['Нет данных']
            : ['Просрочено', 'Закрыто вовремя', 'Меньше часа', 'В работе'],

        datasets: [{
            data: isEmpty ? [1] : values,
            backgroundColor: isEmpty
                ? [theme.empty]
                : [theme.red, theme.green, theme.yellow, theme.blue],
            borderColor: theme.baseBg,
            borderWidth: isEmpty ? 0 : 1
        }]
    };

    const chart = new Chart(canvas, {
        type: 'doughnut',
        data,
        options: {
            cutout: '45%',
            plugins: {
                title: {
                    display: true,
                    text: title,
                    color: theme.text,
                    font: { weight: '400', size: 12 },
                    position: 'top'
                },
                legend: {
                    display: true,
                    position: 'bottom',
                    align: 'start',
                    labels: {
                        color: theme.text,
                        usePointStyle: true,
                        padding: 16
                    }
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: theme.bg,
                    titleColor: theme.text,
                    bodyColor: theme.text,
                    borderColor: theme.grid,
                    borderWidth: 1,
                    callbacks: {
                        label(ctx) {
                            return isEmpty
                                ? 'Нет SLA-данных'
                                : `${ctx.label}: ${ctx.parsed}`;
                        }
                    }
                }
            }
        }
    });

    const observer = new MutationObserver(() => {
        const t = getThemeVars();

        const dataset = chart.data.datasets[0];

        dataset.backgroundColor = isEmpty
            ? [t.empty]
            : [t.red, t.green, t.yellow, t.blue];

        dataset.borderColor = t.baseBg;

        chart.options.plugins.legend.labels.color = t.text;
        chart.options.plugins.title.color = t.text;
        chart.options.plugins.tooltip.backgroundColor = t.bg;
        chart.options.plugins.tooltip.titleColor = t.text;
        chart.options.plugins.tooltip.bodyColor = t.text;

        chart.update();
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
    });

    return chart;
}
