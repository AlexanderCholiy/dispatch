// static/js/users/presence/ui.js
import { PRESENCE_CONFIG } from './config.js';

const AVATARS_CONTAINER_ID = 'presence-avatars-list';
const ADD_COUNT_CONTAINER_ID = 'presence-add-count';
const MAX_VISIBLE_AVATARS = 7; // Максимальное количество видимых аватаров

/**
 * Создает элемент аватара пользователя
 */
function createAvatarElement(user) {
    const wrapper = document.createElement('div');
    wrapper.className = 'tooltip';
    
    // --- ЛОГИКА СОЗДАНИЯ ЗАГОЛОВКА ---
    let namePart = '';
    let rolePart = '';

    // 1. Получаем имя (приоритет: user_str > username)
    if (user.user_str) {
        namePart = user.user_str;
    } else if (user.username) {
        namePart = user.username;
    } else {
        namePart = 'Пользователь'; // Фолбек, если нет ни того, ни другого
    }

    // 2. Получаем роль (если есть)
    if (user.role_str) {
        rolePart = ` (${user.role_str})`;
    }

    // 3. Собираем итоговый текст: "Иванов И (диспетчер)"
    const titleText = namePart + rolePart;
    // ----------------------------------

    wrapper.setAttribute('data-title', titleText);

    const link = document.createElement('a');
    link.className = 'presence-avatar-link'; 
    link.href = `/users/${user.user_id}/`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    
    let contentHtml = '';

    if (user.avatar_url) {
        contentHtml = `<img src="${user.avatar_url}" alt="${namePart}">`;
    } else {
        const firstLetter = user.username && user.username.length > 0 
            ? user.username.charAt(0).toUpperCase() 
            : '?';
            
        contentHtml = `<span class="initials">${firstLetter}</span>`;
    }

    link.innerHTML = contentHtml;
    wrapper.appendChild(link);

    return wrapper;
}

/**
 * Создает элемент счетчика "+N"
 */
function createMoreCountElement(count) {
    const div = document.createElement('div');
    div.className = 'presence-add-count tooltip';
    // Текст подсказки: "Ещё X пользователей"
    div.setAttribute('data-title', `Ещё ${count} гостей`);
    div.textContent = `+${count}`;
    return div;
}

/**
 * Обновление списка пользователей на странице
 * @param {Array} users - Список пользователей (уже отфильтрованный от себя)
 * @param {String} currentUrl - Текущий URL страницы (для логирования или проверки)
 */
export const updateUsersList = (users, currentUrl) => {
    const avatarsContainer = document.getElementById(AVATARS_CONTAINER_ID);
    const addCountContainer = document.getElementById(ADD_COUNT_CONTAINER_ID);

    if (!avatarsContainer) {
        console.warn('[Presence] Avatars container not found.');
        return;
    }

    // Очищаем контейнеры перед рендером
    avatarsContainer.innerHTML = '';
    if (addCountContainer) {
        addCountContainer.innerHTML = '';
        // Скрываем контейнер, если он пустой (или удаляем его из DOM, но лучше скрывать через CSS display:none)
        // Здесь мы просто очистим контент, а CSS сделает его невидимым, если внутри пусто
        addCountContainer.style.display = 'none'; 
    }

    const totalUsers = users.length;

    if (totalUsers === 0) {
        // Если никого нет, ничего не рисуем
        return;
    }

    // Определяем сколько показывать
    const visibleCount = Math.min(totalUsers, MAX_VISIBLE_AVATARS);
    const remainingCount = totalUsers - visibleCount;

    // 1. Рендерим видимые аватары
    for (let i = 0; i < visibleCount; i++) {
        const user = users[i];
        const avatarEl = createAvatarElement(user);
        avatarsContainer.appendChild(avatarEl);
    }

    // 2. Если есть скрытые пользователи, добавляем блок "+N"
    if (remainingCount > 0 && addCountContainer) {
        const moreEl = createMoreCountElement(remainingCount);
        addCountContainer.appendChild(moreEl);
        addCountContainer.style.display = 'flex'; // Показываем контейнер
    }
};

// Функция initWidget теперь не нужна, так как HTML создается в шаблоне
export const initWidget = () => {
    // Ничего не делаем, структура уже есть в HTML
};