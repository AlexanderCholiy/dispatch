// static/js/users/presence/init_skeleton_presence.js
import { connectSocket, fetchUsersOnPage, notifyPageChange, setCallbacks, getSocketState } from './socket.js';
import { initWidget, updateUsersList } from './ui.js';
import { PRESENCE_CONFIG as MODULE_CONFIG } from './config.js';

let currentPath = window.location.pathname;
let refreshIntervalId = null;
let currentUserId = null;

/**
 * Получение ID текущего пользователя из глобальной конфигурации
 * Ожидается, что в base.html установлен window.PRESENCE_CONFIG.currentUser
 */
function getCurrentUserId() {
    if (window.PRESENCE_CONFIG && 
        window.PRESENCE_CONFIG.currentUser && 
        typeof window.PRESENCE_CONFIG.currentUser.id === 'number') {
        return window.PRESENCE_CONFIG.currentUser.id;
    }
    console.warn('[Presence] User ID not found in global config.');
    return null;
}

/**
 * Фильтрация списка: убираем текущего пользователя
 * Сервер возвращает всех, а мы скрываем себя на клиенте
 */
const filterSelf = (users) => {
    if (!currentUserId) return users;
    return users.filter(user => user.user_id !== currentUserId);
};

/**
 * Запуск автоматического обновления списка (опрос сервера)
 */
const startAutoRefresh = () => {
    if (refreshIntervalId) clearInterval(refreshIntervalId);
    
    console.log(`[Presence] Auto-refresh started (${MODULE_CONFIG.AUTO_REFRESH_INTERVAL_MS / 1000}s interval)`);
    
    refreshIntervalId = setInterval(() => {
        const state = getSocketState();
        if (state === WebSocket.OPEN) {
            fetchUsersOnPage(currentPath);
        } else {
            console.warn('[Presence] Socket not ready, skipping auto-refresh');
        }
    }, MODULE_CONFIG.AUTO_REFRESH_INTERVAL_MS);
};

/**
 * Остановка автоматического обновления
 */
const stopAutoRefresh = () => {
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
        console.log('[Presence] Auto-refresh stopped');
    }
};

/**
 * Основная функция инициализации
 */
function init() {
    // Получаем ID пользователя сразу при старте
    currentUserId = getCurrentUserId();
    
    // Создаем виджет
    initWidget();

    // Настраиваем колбэки сокетов
    setCallbacks({
        onOpen: () => {
            console.log('[Presence] Connected');
            // Сразу запрашиваем список пользователей на текущей странице
            fetchUsersOnPage(currentPath);
            // Запускаем периодическое обновление
            startAutoRefresh();
        },
        onMessage: (data) => {
            if (data.type === MODULE_CONFIG.MSG_TYPES.USERS_LIST) {
                // КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Фильтруем себя перед отрисовкой
                // Сервер прислал всех, мы оставляем только "других"
                const filteredUsers = filterSelf(data.users);
                updateUsersList(filteredUsers, data.url);
            }
        },
        onClose: () => {
            console.log('[Presence] Connection closed');
            stopAutoRefresh();
        }
    });

    // Подключаемся к WebSocket
    connectSocket();

    // Настраиваем слушатели навигации
    setupNavigationListeners();
}

/**
 * Настройка слушателей навигации (клики, история)
 */
function setupNavigationListeners() {
    // 1. История браузера (Back/Forward)
    window.addEventListener('popstate', () => {
        const newPath = window.location.pathname;
        if (newPath !== currentPath) {
            notifyPageChange(newPath, currentPath);
            fetchUsersOnPage(newPath);
            currentPath = newPath;
        }
    });

    // 2. Перехват кликов по ссылкам
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        
        // Фильтры: внешние ссылки, якоря, админка, API, загрузки
        if (!href || 
            link.hasAttribute('target') || 
            link.hasAttribute('download') || 
            href.startsWith('#') || 
            href.startsWith('/admin/') || 
            href.startsWith('/api/') ||
            !href.startsWith('/')) {
            return;
        }

        const newPath = new URL(href, window.location.origin).pathname;
        if (newPath !== currentPath) {
            notifyPageChange(newPath, currentPath);
            fetchUsersOnPage(newPath);
            currentPath = newPath;
        }
    });
}

// Запуск после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}