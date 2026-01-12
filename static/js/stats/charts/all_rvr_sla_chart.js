export function renderRvrSlaChart(ctx, stats) {
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: stats.map(i => i.name),
            datasets: [
                {
                    label: 'Просрочено',
                    data: stats.map(i => i.sla_rvr_expired_count),
                },
                {
                    label: 'Выполнено вовремя',
                    data: stats.map(i => i.sla_rvr_closed_on_time_count),
                },
                {
                    label: 'Менее часа',
                    data: stats.map(i => i.sla_rvr_less_than_hour_count),
                },
                {
                    label: 'В процессе',
                    data: stats.map(i => i.sla_rvr_in_progress_count),
                },
            ]
        },
        options: {
            responsive: true,
            stacked: true,
        }
    });
}
