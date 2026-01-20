import { getCssVar, getThemeVars } from './utils.js';

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
                borderRadius: theme.radiusMd,
                // Приоритет переменной над статичным цветом
                backgroundColor: ds.colorVar ? getCssVar(ds.colorVar) : (ds.color || theme.blue),
            }))
        };
    }

    const chart = new Chart(canvas, {
        type: 'bar',
        data: buildData(),
        options: {
            responsive: true,
            maintainAspectRatio: false,
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
                        color: theme.textColor, // Используем основной текст для легенды
                        font: { size: theme.fontSm }
                    }
                },
                tooltip: {
                    backgroundColor: theme.backgroundColor,
                    titleColor: theme.textColor,
                    bodyColor: theme.addTextColor,
                    borderColor: theme.gridColor,
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: theme.radiusMd,
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
                zoom: {
                    pan: { enabled: true, mode: 'x' },
                    zoom: {
                        wheel: { enabled: true },
                        pinch: { enabled: true },
                        mode: 'x'
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: theme.addTextColor,
                        font: { size: theme.fontXs }
                    },
                    grid: { color: theme.gridColor }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: theme.addTextColor,
                        font: { size: theme.fontXs }
                    },
                    grid: { color: theme.gridColor }
                }
            },
            onClick(evt, elements) {
                if (!elements.length) return;
                const index = elements[0].index;
                const region = chart.data.labels[index];

                if (!isFocused) {
                    hiddenRegions = new Set(
                        stats.map(i => i.macroregion).filter(r => r !== region)
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

    canvas.addEventListener('dblclick', () => {
        chart.resetZoom();
    });

    canvas._chartInstance = chart;

    // 🌗 Реакция на смену темы
    const observer = new MutationObserver(() => {
        const t = getThemeVars(); // Здесь определили 't'

        chart.options.plugins.legend.labels.color = t.textColor;
        chart.options.plugins.tooltip.backgroundColor = t.backgroundColor;
        chart.options.plugins.tooltip.titleColor = t.textColor;
        chart.options.plugins.tooltip.bodyColor = t.addTextColor;
        chart.options.plugins.tooltip.borderColor = t.gridColor;

        chart.options.scales.x.ticks.color = t.addTextColor;
        chart.options.scales.y.ticks.color = t.addTextColor;
        chart.options.scales.x.grid.color = t.gridColor;
        chart.options.scales.y.grid.color = t.gridColor;

        chart.data.datasets.forEach((ds, idx) => {
            const source = datasets[idx];
            // Теперь переменная 't' доступна
            ds.backgroundColor = source.colorVar 
                ? getCssVar(source.colorVar) 
                : (source.color || t.blue); 
        });

        chart.update();
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
    });

    return chart;
}
