// static/js/users/presence/init_skeleton_presence.js
import { connectSocket, fetchUsersOnPage, notifyPageChange, setCallbacks, getSocketState } from './socket.js';
import { initWidget, updateUsersList } from './ui.js';
import { PRESENCE_CONFIG as MODULE_CONFIG } from './config.js';

let currentPath = window.location.pathname;
let refreshIntervalId = null;
let currentUserId = null;
// Храним текущий отрисованный список пользователей, чтобы сравнивать с новым
let currentDisplayedUsers = []; 

/**
 * Получение ID текущего пользователя из глобальной конфигурации
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
 */
const filterSelf = (users) => {
    if (!currentUserId) return users;
    return users.filter(user => user.user_id !== currentUserId);
};

/**
 * Глубокое сравнение двух массивов пользователей
 * Сравнивает user_id и статус presence (если он есть), чтобы избежать лишних рендеров
 */
const hasUsersChanged = (newUsers, oldUsers) => {
    // Если длины разные - точно изменилось
    if (newUsers.length !== oldUsers.length) return true;

    // Проходим по каждому элементу
    for (let i = 0; i < newUsers.length; i++) {
        const newUser = newUsers[i];
        const oldUser = oldUsers[i];

        // Если IDs разные или порядок сместился
        if (newUser.user_id !== oldUser.user_id) return true;

        // Если есть поле presence (статус), проверяем и его
        // Если поля нет, считаем что оно одинаковое (или undefined)
        if (newUser.presence !== oldUser.presence) return true;
        
        // Можно добавить проверку других полей, если они влияют на визуал (например, avatar_url обновляется)
        // Но обычно avatar_url статичен, а presence меняется часто.
    }

    return false;
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
    currentUserId = getCurrentUserId();
    initWidget();

    setCallbacks({
        onOpen: () => {
            console.log('[Presence] Connected');
            fetchUsersOnPage(currentPath);
            startAutoRefresh();
        },
        onMessage: (data) => {
            if (data.type === MODULE_CONFIG.MSG_TYPES.USERS_LIST) {
                const filteredUsers = filterSelf(data.users);
                
                // ПРОВЕРКА НА ИЗМЕНЕНИЯ
                // Если список пустой (первый раз) или данные изменились - обновляем
                if (currentDisplayedUsers.length === 0 || hasUsersChanged(filteredUsers, currentDisplayedUsers)) {
                    updateUsersList(filteredUsers, data.url);
                    // Обновляем хранимое состояние
                    currentDisplayedUsers = filteredUsers;
                } else {
                    // Данные не изменились, пропускаем перерисовку
                    console.debug('[Presence] No changes detected, skipping render.');
                }
            }
        },
        onClose: () => {
            console.log('[Presence] Connection closed');
            stopAutoRefresh();
        }
    });

    connectSocket();
    setupNavigationListeners();
}

/**
 * Настройка слушателей навигации
 */
function setupNavigationListeners() {
    window.addEventListener('popstate', () => {
        const newPath = window.location.pathname;
        if (newPath !== currentPath) {
            notifyPageChange(newPath, currentPath);
            fetchUsersOnPage(newPath);
            currentPath = newPath;
        }
    });

    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        
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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}