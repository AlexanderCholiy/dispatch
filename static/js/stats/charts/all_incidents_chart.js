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
        titleColor: styles.getPropertyValue('--color').trim(),
        textColor: styles.getPropertyValue('--add-color').trim(),
        gridColor: styles.getPropertyValue('--extra-color').trim(),
        bgColor: styles.getPropertyValue('--background-color').trim(),
        fontSm: remToPx(styles.getPropertyValue('--font-sm').trim()),
        fontXs: remToPx(styles.getPropertyValue('--font-xs').trim()),
        radius: remToPx(styles.getPropertyValue('--radius-md').trim()),
    };
}

function getCssVar(name, fallback) {
    return (
        getComputedStyle(document.documentElement)
            .getPropertyValue(name)
            .trim() || fallback
    );
}

export function renderAllIncidentsChart(
    canvas,
    stats,
    { title, datasets }
) {
    if (!canvas || !window.Chart) return;

    if (canvas._chartInstance) {
        canvas._chartInstance.destroy();
    }

    const theme = getThemeVars();

    // ===== внутреннее состояние =====
    let hiddenRegions = new Set();
    let isFocused = false;

    function buildData() {
        const filtered = stats.filter(
            i => !hiddenRegions.has(i.macroregion)
        );

        return {
            labels: filtered.map(i => i.macroregion),
            datasets: datasets.map(ds => ({
                label: ds.label,
                data: filtered.map(i => i[ds.valueKey] ?? 0),
                backgroundColor: getCssVar(ds.colorVar, ds.color),
                borderRadius: theme.radius,
            }))
        };
    }

    const chart = new Chart(canvas, {
        type: 'bar',
        data: buildData(),
        options: {
            responsive: true,

            interaction: {
                mode: 'index',
                intersect: false
            },

            plugins: {
                title: {
                    display: false,
                    text: title
                },

                legend: {
                    labels: {
                        color: theme.titleColor,
                        font: { size: theme.fontSm }
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
                        },
                    }
                },

                // 🔍 zoom + pan
                zoom: {
                    pan: {
                        enabled: true,
                        mode: 'x'
                    },
                    zoom: {
                        wheel: {
                            enabled: true
                        },
                        pinch: {
                            enabled: true
                        },
                        mode: 'x'
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
            },

            // 🎯 клик по региону = фокус
            onClick(evt, elements) {
                if (!elements.length) return;

                const index = elements[0].index;
                const region = chart.data.labels[index];

                if (!isFocused) {
                    hiddenRegions = new Set(
                        stats
                            .map(i => i.macroregion)
                            .filter(r => r !== region)
                    );
                    isFocused = true;
                } else {
                    hiddenRegions.clear();
                    isFocused = false;
                }

                chart.data = buildData();
                chart.update();
            }
        }
    });

    // 🔄 double click = reset zoom
    canvas.addEventListener('dblclick', () => {
        chart.resetZoom();
    });

    canvas._chartInstance = chart;

    // 🌗 реакция на смену темы
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

        chart.data.datasets.forEach((ds, idx) => {
            const source = datasets[idx];
            ds.backgroundColor = getCssVar(
                source.colorVar,
                source.color
            );
        });

        chart.update();
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
    });

    return chart;
}
