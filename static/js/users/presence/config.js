// static/js/users/presence/config.js

export const PRESENCE_CONFIG = {
    // Маршрут WebSocket
    ENDPOINT: '/ws/presence/',
    
    // Настройки переподключения
    MAX_RECONNECT_ATTEMPTS: 5,
    RECONNECT_DELAY_BASE: 3000, // 3 секунды
    
    // Интервал авто-обновления (мс)
    // 1000 = 1 сек (для тестов), поставьте 10000 (10 сек) для продакшена
    AUTO_REFRESH_INTERVAL_MS: 1000, 
    
    // Fallback аватар
    DEFAULT_AVATAR: '/static/img/fav/favicon.ico',
    
    // Типы сообщений
    MSG_TYPES: {
        PAGE_CHANGE: 'page_change',
        GET_USERS: 'get_users',
        USERS_LIST: 'users_list'
    }
};

/**
 * Определяет протокол (wss для https, ws для http)
 */
export const getProtocol = () => {
    return window.location.protocol === "https:" ? "wss" : "ws";
};

/**
 * Формирует полный URL для WebSocket
 */
export const getWebSocketUrl = () => {
    const protocol = getProtocol();
    const host = window.location.host;
    return `${protocol}://${host}${PRESENCE_CONFIG.ENDPOINT}`;
};