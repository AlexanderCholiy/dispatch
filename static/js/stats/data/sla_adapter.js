export function adaptSla(apiItem, type) {
    if (type === 'avr') {
        return [
            apiItem.sla_avr_expired_count ?? 0,
            apiItem.sla_avr_closed_on_time_count ?? 0,
            apiItem.sla_avr_less_than_hour_count ?? 0,
            apiItem.sla_avr_in_progress_count ?? 0,
        ];
    }

    if (type === 'rvr') {
        return [
            apiItem.sla_rvr_expired_count ?? 0,
            apiItem.sla_rvr_closed_on_time_count ?? 0,
            apiItem.sla_rvr_less_than_hour_count ?? 0,
            apiItem.sla_rvr_in_progress_count ?? 0,
        ];
    }

    return [];
}