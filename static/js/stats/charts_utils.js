/**
 * Возвращает массив дат от 1 числа предыдущего месяца по сегодня в формате YYYY-MM-DD
 * Коррекция для часового пояса (используем UTC)
 */
export function getDatesSincePreviousMonth() {
    const dates = [];
    const today = new Date();
    const firstDayPrevMonth = getFirstDayOfPreviousMonth();

    for (let d = new Date(firstDayPrevMonth.getTime()); d <= today; d.setUTCDate(d.getUTCDate() + 1)) {
        const year = d.getUTCFullYear();
        const month = String(d.getUTCMonth() + 1).padStart(2, '0');
        const day = String(d.getUTCDate()).padStart(2, '0');
        dates.push(`${year}-${month}-${day}`);
    }

    return dates;
}

/**
 * Возвращает Date, соответствующую 1 числу предыдущего месяца
 * Используем локальные значения, чтобы не зависеть от часового пояса
 */
export function getFirstDayOfPreviousMonth() {
    const today = new Date();
    let year = today.getFullYear();
    let month = today.getMonth() - 1;

    if (month < 0) {
        month = 11;
        year -= 1;
    }

    // Создаём дату в UTC, чтобы корректно работала toISOString
    return new Date(Date.UTC(year, month, 1));
}

/**
 * Форматирует дату Date в строку YYYY-MM-DD (UTC)
 */
export function formatDate(date) {
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const day = String(date.getUTCDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

export function formatDateRu(date) {
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        timeZone: 'UTC',
    });
}
