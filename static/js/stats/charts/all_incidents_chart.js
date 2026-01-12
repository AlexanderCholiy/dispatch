function remToPx(value) {
    if (!value) return 14;
    if (value.endsWith('rem')) {
        const base = parseFloat(
            getComputedStyle(document.documentElement).fontSize
        );
        return parseFloat(value) * base;
    }
    return parseFloat(value);
}

function getThemeVars() {
    const styles = getComputedStyle(document.documentElement);

    return {
        textColor: styles.getPropertyValue('--add-color').trim(),
        gridColor: styles.getPropertyValue('--extra-color').trim(),
        bgColor: styles.getPropertyValue('--background-color').trim(),
        fontSm: remToPx(styles.getPropertyValue('--font-sm').trim()),
        fontXs: remToPx(styles.getPropertyValue('--font-xs').trim()),
        radius: remToPx(styles.getPropertyValue('--radius-md').trim()),
    };
}

export function renderAllIncidentsChart(
    canvas,
    stats,
    { title, label, valueKey, color }
) {
    if (!canvas || !window.Chart) return;

    if (canvas._chartInstance) {
        canvas._chartInstance.destroy();
    }

    const labels = stats.map(i => i.macroregion);
    const values = stats.map(i => i[valueKey] ?? 0);

    const theme = getThemeVars();

    const chart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label,
                    data: values,
                    backgroundColor: color,
                    borderRadius: theme.radius,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: {
                        color: theme.textColor,
                        font: {
                            size: theme.fontSm
                        }
                    }
                },

                tooltip: {
                    backgroundColor: theme.bgColor,
                    titleColor: theme.textColor,
                    bodyColor: theme.textColor,
                    borderColor: theme.gridColor,
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: theme.radius,
                    titleFont: {
                        size: theme.fontSm,
                        weight: '600'
                    },
                    bodyFont: {
                        size: theme.fontXs
                    },
                    callbacks: {
                        label(ctx) {
                            return `${ctx.dataset.label}: ${ctx.parsed.y}`;
                        }
                    }
                }
            },

            scales: {
                x: {
                    ticks: {
                        color: theme.textColor,
                        font: { size: theme.fontXs }
                    },
                    grid: { color: theme.gridColor }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: theme.textColor,
                        font: { size: theme.fontXs }
                    },
                    grid: { color: theme.gridColor }
                }
            }
        }
    });

    canvas._chartInstance = chart;

    // 🔁 Реакция на смену темы
    const observer = new MutationObserver(() => {
        const theme = getThemeVars();

        chart.options.plugins.legend.labels.color = theme.textColor;
        chart.options.plugins.tooltip.backgroundColor = theme.bgColor;
        chart.options.plugins.tooltip.titleColor = theme.textColor;
        chart.options.plugins.tooltip.bodyColor = theme.textColor;
        chart.options.scales.x.ticks.color = theme.textColor;
        chart.options.scales.y.ticks.color = theme.textColor;
        chart.options.scales.x.grid.color = theme.gridColor;
        chart.options.scales.y.grid.color = theme.gridColor;

        chart.update();
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
    });

    return chart;
}
