export async function loadStatisticsAll() {
    const response = await fetch('/api/v1/report/statistics/');
    if (!response.ok) {
        throw new Error('Failed to load all statistics');
    }
    return response.json();
}

export async function loadStatisticsFromDate(startDate) {
    const response = await fetch(
        `/api/v1/report/statistics/?start_date=${startDate}`
    );
    if (!response.ok) {
        throw new Error('Failed to load filtered statistics');
    }
    return response.json();
}
