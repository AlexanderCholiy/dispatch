document.addEventListener('DOMContentLoaded', () => {
  // Получаем элементы кнопки и иконки
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon = document.getElementById('theme-icon');
  
  // Если кнопки нет (например, на других страницах), выходим
  if (!themeToggle) return;

  // Массив тем в порядке переключения
  const themes = ['light', 'dark', 'auto'];
  
  // Иконки и подсказки
  const icons = { light: 'bx-sun', dark: 'bx-moon', auto: 'bx-desktop' };
  const titles = { light: 'Светлая тема', dark: 'Тёмная тема', auto: 'Системная тема' };

  // Функция получения темы из Cookie
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  // Функция установки Cookie
  function setCookie(name, value, days) {
    let expires = "";
    if (days) {
      const date = new Date();
      date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
      expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
  }

  // Логика переключения при клике
  themeToggle.addEventListener('click', () => {
    // Текущая тема (из Cookie или дефолт 'auto')
    let currentTheme = getCookie('site_theme') || 'auto';
    
    // Находим индекс текущей темы
    let index = themes.indexOf(currentTheme);
    
    // Вычисляем следующую тему (циклично)
    let nextIndex = (index + 1) % themes.length;
    let nextTheme = themes[nextIndex];

    // Сохраняем новую тему в Cookie на 30 дней
    setCookie('site_theme', nextTheme, 30);

    // Обновляем иконку и подсказку сразу (чтобы пользователь видел изменение)
    if (themeIcon) themeIcon.className = 'bx ' + icons[nextTheme];
    themeToggle.setAttribute('data-title', titles[nextTheme]);

    // ПЕРЕЗАГРУЖАЕМ СТРАНИЦУ
    // Django прочитает новую куку и сформирует новый URL для iframe с правильным theme
    window.location.reload();
  });

  // Применяем тему при первой загрузке страницы
  const savedTheme = getCookie('site_theme') || 'auto';
  if (savedTheme !== 'auto') {
    if (themeIcon) themeIcon.className = 'bx ' + icons[savedTheme];
    themeToggle.setAttribute('data-title', titles[savedTheme]);
  } else {
    // Для авто-темы смотрим системную настройку
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const systemTheme = prefersDark ? 'dark' : 'light';
    if (themeIcon) themeIcon.className = 'bx ' + icons[systemTheme];
    themeToggle.setAttribute('data-title', titles['auto']);
  }
});