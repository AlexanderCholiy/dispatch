import { getChartColors } from '../theme_colors.js';

// Плагин текста в центре
export function centerTextPlugin() {
    return {
        id: 'centerText',
        afterDraw(chart) {
            const meta = chart.getDatasetMeta(0);
            if (!meta?.data?.length) return;

            const { ctx } = chart;
            const { x, y } = meta.data[0];

            const colors = getChartColors();

            const hasData = chart.$hasData === true;
            const total = chart.$total ?? 0;

            ctx.save();
            ctx.font = '600 20px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            ctx.fillStyle = hasData
                ? chart.options.plugins.title.color
                : colors.gray;

            ctx.fillText(hasData ? total : 0, x, y);
            ctx.restore();
        }
    };
}
