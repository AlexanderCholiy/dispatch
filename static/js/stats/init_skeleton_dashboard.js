import { createDailyIncidentsChart, updateDailyIncidentsChartColors } from './charts/daily_incidents.js';
import { createAllIncidentsChart, updateAllIncidentsChartColors } from './charts/all_incidents.js';
import { createSlaDonutChart, updateSlaDonutChartColors } from './charts/sla_donut.js';
import { getDatesSincePreviousMonth } from './charts_utils.js';
import { getChartColors, observeThemeChange } from './theme_colors.js';
import { updateCopyButton, updateSlaCopyData } from './data/copy_chart_data.js';
import { startStatisticsWebSocket } from './dashboard_ws_updater.js';
import { initWeeklyMacroregionsTable } from './data/weekly_macroregions_table.js';
import { getFirstDayOfPreviousMonth } from './charts_utils.js';
import { initAvrContractorsTable } from './data/avr_contractors_table.js';


if (window.Chart && window.ChartZoom) {
    Chart.register(window.ChartZoom);
}

window.dashboardCharts = {};


/* =====================================================
   COLOR KEYS CONFIG (единый источник истины)
===================================================== */

const DAILY_COLOR_KEYS = [
    'gray','pink','cyan','blue','red',
    'yellow','brown','slate','magenta','green','extra'
];

const TYPES_COLOR_KEYS = [
    'blue','red','green','yellow','gray','cyan'
];

const CLOSED_COLOR_KEYS = ['green','gray'];
const OPEN_COLOR_KEYS = ['blue','gray'];

const POWER_SUBTYPE_COLOR_KEYS = [
    'magenta','pink','purple','lime','orange',
    'teal','green','indigo','cyan','yellow',
    'blue','brown','amber','red','gray',
    'slate','extra'
];

function resolveColors(keys) {
    const colors = getChartColors();
    return keys.map(k => colors[k]);
}


/* =====================================================
   INIT
===================================================== */

document.addEventListener('DOMContentLoaded', () => {

    const colors = getChartColors();

    /* ---------- DAILY ---------- */

    const dailyDatasets = DAILY_COLOR_KEYS.map((key, idx) => ({
        label: `МР-${idx + 1}`,
        data: [],
        borderColor: colors[key],
        backgroundColor: colors[key],
        fill: false
    }));

    const dailyChart = createDailyIncidentsChart(
        document.getElementById('daily-incidents-chart').getContext('2d'),
        { labels: getDatesSincePreviousMonth(), datasets: dailyDatasets }
    );

    window.dashboardCharts.daily = dailyChart;

    updateCopyButton('daily-chart-card', dailyChart, 'Дата/Регион');

    /* ---------- MACROREGIONS ---------- */

    const MACROREGION_LABELS = [
        'ALL','МР-1','МР-2','МР-3','МР-4',
        'МР-5','МР-6','МР-7','МР-8','МР-9'
    ];

    //* ---------- WEEKLY TABLE ---------- */

    const start = getFirstDayOfPreviousMonth();
    const end = new Date();

    initWeeklyMacroregionsTable(
        'weekly-incidents-table',
        null,
        start,
        end
    );


    /* ---------- CLOSED ---------- */

    const closedChart = createAllIncidentsChart(
        document.getElementById('all-closed-incidents-chart').getContext('2d'),
        {
            labels: MACROREGION_LABELS,
            datasets: [
                { label:'Всего', data:[], backgroundColor: colors.green },
                { label:'Без питания', data:[], backgroundColor: colors.gray }
            ]
        },
        'Закрытые'
    );

    window.dashboardCharts.closed = closedChart;

    updateCopyButton(
        'closed-chart-card',
        closedChart,
        'Регион/Количество инцидентов'
    );


    /* ---------- OPEN ---------- */

    const openChart = createAllIncidentsChart(
        document.getElementById('all-open-incidents-chart').getContext('2d'),
        {
            labels: MACROREGION_LABELS,
            datasets: [
                { label:'Всего', data:[], backgroundColor: colors.blue },
                { label:'Без питания', data:[], backgroundColor: colors.gray }
            ]
        },
        'Открытые'
    );

    window.dashboardCharts.open = openChart;

    updateCopyButton(
        'open-chart-card',
        openChart,
        'Регион/Количество инцидентов'
    );


    /* ---------- TYPES ---------- */

    const typesDatasets = [
        'Авария по питанию',
        'Инцидент по конструктиву / территорией АМС',
        'Инцидент / запрос гос. органов',
        'Авария ВОЛС',
        'Угроза гибели / гибель объекта',
        'Запрос на организацию доступа к объекту'
    ];

    const typesChart = createAllIncidentsChart(
        document.getElementById('types-incidents-chart').getContext('2d'),
        {
            labels: MACROREGION_LABELS,
            datasets: typesDatasets.map((label,i)=>({
                label,
                data:[],
                backgroundColor: resolveColors(TYPES_COLOR_KEYS)[i]
            }))
        },
        'Классификация аварий',
        true
    );

    window.dashboardCharts.types = typesChart;

    updateCopyButton(
        'types-chart-card',
        typesChart,
        'Регион/Тип аварии'
    );


    /* ---------- POWER SUBTYPES ---------- */

    const powerSubtypeLabels = [
        'ЗО НБ. ВЛ до 1 кВ',
        'ЗО НБ. ВЛ свыше 1 кВ',
        'ЗО НБ. КЛ до 1 кВ',
        'ЗО НБ. КЛ свыше 1 кВ',
        'ЗО НБ. КТП',
        'ЗО НБ. ПУ/АИИСКУЭ',
        'ЗО НБ. РЩ/РУ',
        'ЗО Оператора. Линия',
        'ЗО Оператора. Оборудование ЭУ',
        'ЗО Сетевой организации. Аварийные работы',
        'ЗО Сетевой организации. Плановые работы',
        'Прочее (форс-мажор)',
        'Отключение за неоплату',
        'Самовосстановление питания',
        'ШЭП',
        'Отсутствие схемы',
        'Без подкатегории'
    ];

    const powerIssueSubtypesChart = createAllIncidentsChart(
        document.getElementById(
            'energy-subtypes-incidents-chart'
        ).getContext('2d'),
        {
            labels: MACROREGION_LABELS,
            datasets: powerSubtypeLabels.map((label,i)=>({
                label,
                data:[],
                backgroundColor: resolveColors(
                    POWER_SUBTYPE_COLOR_KEYS
                )[i]
            }))
        },
        'Аварии по питанию (подкатегории)',
        true
    );

    window.dashboardCharts.subtypes = {
        power:{
            chart:powerIssueSubtypesChart,
            labels:powerSubtypeLabels
        }
    };

    updateCopyButton(
        'energy-subtypes-chart-card',
        powerIssueSubtypesChart,
        'Регион/Подкатегория аварии по питанию'
    );

    /* ---------- SLA ---------- */
    const initSlaSkeleton = (containerId, title) => {
        const container = document.getElementById(containerId);
        const charts = [];

        if (!container) {
            console.error(`Container ${containerId} not found`);
            return charts;
        }

        // Удаляем все дочерние элементы кроме .chart-utils и таблицы AVR
        container
            .querySelectorAll(':scope > *:not(.chart-utils):not(#avr-contractors-table)')
            .forEach(el => el.remove());

        // Заголовок SLA
        const titleEl = document.createElement('p');
        titleEl.className = 'sla-title';
        titleEl.textContent = title;
        container.appendChild(titleEl);

        // Создаём сетку графиков
        const grid = document.createElement('div');
        grid.className = 'sla-grid';
        container.appendChild(grid);

        // Создаём 10 графиков
        for (let i = 1; i <= 10; i++) {
            const item = document.createElement('div');
            item.className = 'sla-item';

            const canvas = document.createElement('canvas');
            item.appendChild(canvas);
            grid.appendChild(item);

            const chart = createSlaDonutChart(
                canvas.getContext('2d'),
                {
                    title: `МР-${i}`,
                    single: true,
                    data: [],
                    datasetColors: [],
                    total: 0
                }
            );
            charts.push(chart);
        }

        // Добавляем таблицу только для AVR
        if (containerId === 'avr-sla-grid') {
            const tableContainer = document.createElement('div');
            tableContainer.className = 'avr-contractors-container table-wrapper';
            tableContainer.id = 'avr-contractors-table';

            // Добавляем контейнер в DOM
            container.appendChild(tableContainer);

            // Инициализация таблицы с пустыми данными
            setTimeout(() => {
                const tableElement = document.getElementById('avr-contractors-table');
                if (tableElement) {
                    try {
                        // Создаём строку с пустыми значениями для placeholders
                        const emptyData = [{
                            contractor_name: '—',
                            total_incidents_for_sla: 0,
                            on_time_percentage: 0,
                            macroregions: [{
                                macroregion: '—',
                                sla_expired_count: 0,
                                sla_closed_on_time_count: 0,
                                sla_waiting_count: 0,
                                sla_in_progress_count: 0
                            }]
                        }];

                        // Инициализируем таблицу
                        initAvrContractorsTable(tableElement, emptyData);
                    } catch (error) {
                        console.error('Ошибка инициализации таблицы AVR:', error);
                    }
                } else {
                    console.error('avr-contractors-table не найден в DOM после добавления!');
                }
            }, 0);
        }

        // Копирование данных
        const copyBtn = container.querySelector('.copy-chart-data-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                if (window.dashboardCharts.lastSlaData) {
                    let type = 'avr';
                    if (containerId.includes('rvr')) type = 'rvr';
                    else if (containerId.includes('dgu')) type = 'dgu';

                    updateSlaCopyData(containerId, window.dashboardCharts.lastSlaData, type);
                    navigator.clipboard.writeText(copyBtn.dataset.text || '');
                }
            });
        }

        return charts;
    };

    window.dashboardCharts.sla = {
        avr: initSlaSkeleton('avr-sla-grid', 'SLA АВР'),
        rvr: initSlaSkeleton('rvr-sla-grid', 'SLA РВР'),
        dgu: initSlaSkeleton('dgu-sla-grid', 'ВРТ РВР')
    };

    /* ---------- DATA ---------- */

    startStatisticsWebSocket(window.dashboardCharts);


    /* =====================================================
       THEME CHANGE
    ===================================================== */

    observeThemeChange(()=>{

        updateDailyIncidentsChartColors(
            window.dashboardCharts.daily,
            resolveColors(DAILY_COLOR_KEYS)
        );

        updateAllIncidentsChartColors(
            window.dashboardCharts.closed,
            resolveColors(CLOSED_COLOR_KEYS)
        );

        updateAllIncidentsChartColors(
            window.dashboardCharts.open,
            resolveColors(OPEN_COLOR_KEYS)
        );

        updateAllIncidentsChartColors(
            window.dashboardCharts.types,
            resolveColors(TYPES_COLOR_KEYS)
        );

        updateAllIncidentsChartColors(
            window.dashboardCharts.subtypes.power.chart,
            resolveColors(POWER_SUBTYPE_COLOR_KEYS)
        );

        updateSlaDonutChartColors(
            window.dashboardCharts.sla.avr
        );

        updateSlaDonutChartColors(
            window.dashboardCharts.sla.rvr
        );

        updateSlaDonutChartColors(
            window.dashboardCharts.sla.dgu
        );

    });

});
