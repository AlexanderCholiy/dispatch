// static/js/users/presence/ui.js
import { PRESENCE_CONFIG } from './config.js';

const AVATARS_CONTAINER_ID = 'presence-avatars-list';
const ADD_COUNT_CONTAINER_ID = 'presence-add-count';
const MAX_VISIBLE_AVATARS = 5; // Максимальное количество видимых аватаров

/**
 * Создает элемент аватара пользователя
 */
function createAvatarElement(user) {
    // 1. Создаем обертку div с классом tooltip и атрибутом data-title
    const wrapper = document.createElement('div');
    wrapper.className = 'tooltip';
    
    // Устанавливаем заголовок для тултипа
    const titleText = user.user_str || user.username;
    wrapper.setAttribute('data-title', titleText);

    // 2. Создаем ссылку a
    const link = document.createElement('a');
    link.className = 'presence-avatar-link';
    link.href = `/users/${user.user_id}/`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    
    let contentHtml = '';

    if (user.avatar_url) {
        // Если есть картинка
        contentHtml = `<img src="${user.avatar_url}" alt="${user.username}">`;
    } else {
        // Если нет картинки - инициалы
        const firstLetter = user.username ? user.username.charAt(0).toUpperCase() : '?';
        contentHtml = `<span class="initials">${firstLetter}</span>`;
    }

    // Вставляем контент в ссылку
    link.innerHTML = contentHtml;

    // 3. Вставляем ссылку в обертку
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