// static/js/users/presence/socket.js
import { getWebSocketUrl, PRESENCE_CONFIG } from './config.js';

let socket = null;
let reconnectAttempts = 0;
let onMessageCallback = null;
let onOpenCallback = null;
let onCloseCallback = null;

/**
 * Установка колбэков для обработки событий сокета
 */
export const setCallbacks = ({ onMessage, onOpen, onClose }) => {
    onMessageCallback = onMessage;
    onOpenCallback = onOpen;
    onCloseCallback = onClose;
};

/**
 * Отправка сообщения через WebSocket
 */
export const sendMessage = (type, url, oldUrl = null) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
        const payload = { type, url, old_url: oldUrl };
        socket.send(JSON.stringify(payload));
    } else {
        console.warn('[Presence] Socket not ready, message dropped:', payload);
    }
};

/**
 * Подключение к WebSocket
 */
export const connectSocket = () => {
    const url = getWebSocketUrl();
    console.log(`[Presence] Connecting to ${url}...`);

    socket = new WebSocket(url);

    socket.onopen = (e) => {
        console.log('[Presence] Connected');
        reconnectAttempts = 0;
        if (onOpenCallback) onOpenCallback(e);
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (onMessageCallback) onMessageCallback(data);
        } catch (e) {
            console.error('[Presence] Parse error:', e);
        }
    };

    socket.onclose = (e) => {
        console.warn(`[Presence] Disconnected (Code: ${e.code})`);
        
        if (onCloseCallback) onCloseCallback(e);

        // Логика экспоненциальной задержки переподключения
        if (reconnectAttempts < PRESENCE_CONFIG.MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            const delay = PRESENCE_CONFIG.RECONNECT_DELAY_BASE * Math.pow(2, reconnectAttempts - 1);
            console.log(`[Presence] Reconnecting in ${delay}ms (Attempt ${reconnectAttempts})...`);
            setTimeout(connectSocket, delay);
        } else {
            console.error('[Presence] Max reconnect attempts reached.');
        }
    };

    socket.onerror = (error) => {
        console.error('[Presence] WebSocket error:', error);
    };
};

/**
 * Запрос списка пользователей на странице
 */
export const fetchUsersOnPage = (path) => {
    sendMessage(PRESENCE_CONFIG.MSG_TYPES.GET_USERS, path);
};

/**
 * Уведомление о переходе на новую страницу
 */
export const notifyPageChange = (newPath, oldPath) => {
    sendMessage(PRESENCE_CONFIG.MSG_TYPES.PAGE_CHANGE, newPath, oldPath);
};

/**
 * Получение текущего состояния сокета (для проверки извне)
 */
export const getSocketState = () => socket ? socket.readyState : -1;