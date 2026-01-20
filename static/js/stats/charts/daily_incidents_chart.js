import { getThemeVars, getCssVar } from './utils.js';

const regionColorVars = [
    '--pink-color',
    '--cyan-color',
    '--blue-color',
    '--red-color',
    '--yellow-color',
    '--brown-color',
    '--gray-color',
    '--magenta-color',
    '--green-color',
    '--orange-color',
];

export function renderDailyIncidentsChart(canvas, stats, options = {}) {
    const { 
        title, 
        empty = false, 
        skeletonLabels = [], 
        lineColor = '#ccc',
        yMax = null,
        yMin = 0
    } = options;

    if (!canvas || !window.Chart) return;

    if (canvas._chartInstance) {
        canvas._chartInstance.destroy();
    }

    const theme = getThemeVars();
    let labels = [];
    let datasets = [];

    if (empty) {
        // Режим скелетона: рисуем пустую серую линию по переданным датам
        labels = skeletonLabels;
        datasets = [{
            label: 'Загрузка...',
            data: labels.map(() => 0), // Линия на нуле
            borderColor: lineColor,
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 0, // Скрываем точки в скелетоне
            tension: 0.3,
            fill: false
        }];
    } else {
        // Основной режим: обработка данных
        const dateSet = new Set();
        stats.forEach(region => {
            Object.keys(region.daily_incidents || {}).forEach(date => dateSet.add(date));
        });
        
        labels = Array.from(dateSet).sort();

        datasets = stats.map((region, idx) => {
            const daily = region.daily_incidents || {};
            // Берем имя переменной по индексу
            const colorVar = regionColorVars[idx % regionColorVars.length];
            const color = getCssVar(colorVar); 

            return {
                label: region.macroregion,
                data: labels.map(date => daily[date] ?? 0),
                borderColor: color,
                backgroundColor: color,
                colorVar: colorVar, 
                borderWidth: 2,
                tension: 0.3,
                fill: false
            };
        });
    }

    const chart = new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: empty ? false : { duration: 1000 }, // Отключаем анимацию для скелетона
            plugins: {
                title: {
                    display: true,
                    text: title,
                    color: theme.titleColor,
                    font: { size: theme.fontSm, weight: 'normal' }
                },
                legend: {
                    display: !empty, // Прячем легенду в скелетоне
                    position: 'bottom',
                    labels: { color: theme.addTextColor }
                },
                tooltip: {
                    enabled: !empty // Отключаем подсказки в скелетоне
                },
                zoom: {
                    pan: { enabled: !empty, mode: 'x' },
                    zoom: {
                        wheel: { enabled: !empty },
                        pinch: { enabled: !empty },
                        mode: 'x'
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: theme.addTextColor,
                        maxRotation: 45,
                        minRotation: 45
                    },
                    grid: { color: theme.gridColor }
                },
                y: {
                    min: yMin,
                    max: yMax, // Используем yMax из опций (в скелетоне передано 1)
                    beginAtZero: true,
                    ticks: { 
                        color: theme.addTextColor,
                        stepSize: empty ? 1 : null 
                    },
                    grid: { color: theme.gridColor }
                }
            }
        }
    });

    // 🌗 Реакция на смену темы
    const observer = new MutationObserver(() => {
        // Проверяем, существует ли еще canvas в DOM, чтобы не вызвать ошибку Chart.js
        if (!document.contains(canvas)) {
            observer.disconnect();
            return;
        }

        const t = getThemeVars();
        chart.options.plugins.title.color = t.titleColor;
        chart.options.plugins.legend.labels.color = t.addTextColor;
        chart.options.scales.x.ticks.color = t.addTextColor;
        chart.options.scales.y.ticks.color = t.addTextColor;
        chart.options.scales.x.grid.color = t.gridColor;
        chart.options.scales.y.grid.color = t.gridColor;

        chart.data.datasets.forEach((ds) => {
            if (empty) {
                ds.borderColor = t.gridColor;
            } else if (ds.colorVar) {
                const newColor = getCssVar(ds.colorVar);
                ds.borderColor = newColor;
                ds.backgroundColor = newColor;
            }
        });

        chart.update('none'); // Обновляем без анимации для стабильности
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
    });

    canvas._chartObserver = observer;
    canvas._chartInstance = chart;

    if (!empty) {
        canvas.addEventListener('dblclick', () => chart.resetZoom());
    }

    return chart;
}
