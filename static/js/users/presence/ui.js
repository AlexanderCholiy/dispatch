// static/js/users/presence/ui.js
import { PRESENCE_CONFIG } from './config.js';

const WIDGET_ID = 'presence-widget';
const LIST_ID = 'presence-list';
const COUNT_ID = 'presence-count';

/**
 * Инициализация или возврат существующего виджета
 */
export const initWidget = () => {
    let widget = document.getElementById(WIDGET_ID);
    if (widget) return widget;

    widget = document.createElement('div');
    widget.id = WIDGET_ID;
    
    // Стили виджета
    Object.assign(widget.style, {
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        width: '320px',
        maxHeight: '400px',
        background: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: '12px',
        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        zIndex: '9999',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        transition: 'transform 0.3s ease, opacity 0.3s ease'
    });

    // Заголовок
    const header = document.createElement('div');
    header.style.cssText = 'padding: 12px 16px; border-bottom: 1px solid #f3f4f6; background: #f9fafb; display: flex; justify-content: space-between; align-items: center;';
    header.innerHTML = `
        <span style="font-weight: 600; font-size: 14px; color: #111827;">Онлайн пользователи</span>
        <span id="${COUNT_ID}" style="font-size: 12px; color: #6b7280; background: #e5e7eb; padding: 2px 8px; border-radius: 12px;">0</span>
    `;
    widget.appendChild(header);

    // Список
    const listContainer = document.createElement('div');
    listContainer.id = LIST_ID;
    listContainer.style.cssText = 'flex: 1; overflow-y: auto; padding: 8px; min-height: 50px; scrollbar-width: thin; scrollbar-color: #cbd5e1 #f1f5f9;';
    
    // Стили скроллбара для Webkit
    const styleSheet = document.createElement("style");
    styleSheet.innerText = `
        #${LIST_ID}::-webkit-scrollbar { width: 6px; }
        #${LIST_ID}::-webkit-scrollbar-track { background: #f1f5f9; }
        #${LIST_ID}::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 10px; }
    `;
    document.head.appendChild(styleSheet);

    widget.appendChild(listContainer);
    document.body.appendChild(widget);

    return widget;
};

/**
 * Рендер одного элемента пользователя
 */
const renderUserItem = (user) => {
    const item = document.createElement('div');
    item.className = 'presence-user-item';
    item.style.cssText = 'display: flex; align-items: center; padding: 8px; margin-bottom: 4px; border-radius: 8px; transition: background 0.2s; cursor: default;';
    
    item.onmouseenter = () => item.style.background = '#f3f4f6';
    item.onmouseleave = () => item.style.background = 'transparent';

    const avatarUrl = user.avatar_url || PRESENCE_CONFIG.DEFAULT_AVATAR;
    
    const avatar = document.createElement('img');
    avatar.src = avatarUrl;
    avatar.alt = user.username;
    avatar.style.cssText = 'width: 36px; height: 36px; border-radius: 50%; object-fit: cover; margin-right: 12px; border: 2px solid #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.1);';

    const info = document.createElement('div');
    info.style.flex = '1';

    const nameRow = document.createElement('div');
    nameRow.style.display = 'flex';
    nameRow.style.alignItems = 'center';
    nameRow.style.gap = '8px';

    const name = document.createElement('strong');
    name.textContent = user.username;
    name.style.cssText = 'font-size: 14px; color: #1f2937;';

    const role = document.createElement('span');
    role.textContent = user.role_str ? `(${user.role_str})` : '';
    role.style.cssText = 'font-size: 11px; color: #6b7280; background: #f3f4f6; padding: 1px 6px; border-radius: 4px;';

    nameRow.appendChild(name);
    nameRow.appendChild(role);

    const action = document.createElement('div');
    action.textContent = user.action || 'На странице';
    action.style.cssText = 'font-size: 12px; color: #9ca3af; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px;';

    info.appendChild(nameRow);
    info.appendChild(action);

    item.appendChild(avatar);
    item.appendChild(info);
    return item;
};

/**
 * Обновление всего списка пользователей
 */
export const updateUsersList = (users, currentUrl) => {
    const container = document.getElementById(LIST_ID);
    const countBadge = document.getElementById(COUNT_ID);
    if (!container || !countBadge) return;

    container.innerHTML = '';
    countBadge.textContent = users.length;

    if (users.length === 0) {
        const empty = document.createElement('div');
        empty.style.cssText = 'text-align: center; padding: 20px; color: #9ca3af; font-size: 13px;';
        empty.textContent = 'Никого нет на этой странице';
        container.appendChild(empty);
        return;
    }

    users.forEach(user => {
        container.appendChild(renderUserItem(user));
    });
};