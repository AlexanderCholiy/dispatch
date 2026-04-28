document.addEventListener('DOMContentLoaded', () => {
  const themes = ['light', 'dark', 'auto'];
  const themeIcon = document.getElementById('theme-icon');
  const themeToggle = document.getElementById('theme-toggle');
  const html = document.documentElement || document.getElementsByTagName('html')[0];
  
  const themeIcons = {
    light: 'bx-sun',
    dark: 'bx-moon',
    auto: 'bx-desktop'
  };
  const themeTitles = {
    light: 'Светлая тема',
    dark: 'Тёмная тема',
    auto: 'Системная тема'
  };

  // --- Функции для работы с Cookies (вместо localStorage) ---
  function setCookie(name, value, days) {
    let expires = "";
    if (days) {
      const date = new Date();
      date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
      expires = "; expires=" + date.toUTCString();
    }
    // Путь '/' делает куку доступной для всего сайта (важно для Django)
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
  }

  function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for(let i=0;i < ca.length;i++) {
      let c = ca[i];
      while (c.charAt(0)==' ') c = c.substring(1,c.length);
      if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
  }
  // -----------------------------------------------------------

  function applyTheme(theme) {
    // Убираем старые темы
    html.classList.remove('light', 'dark');
    
    if (theme === 'light') {
      html.classList.add('light');
    } else if (theme === 'dark') {
      html.classList.add('dark');
    } else if (theme === 'auto') {
      // Если авто, смотрим системную настройку
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const autoTheme = prefersDark ? 'dark' : 'light';
      html.classList.add(autoTheme);
    }

    if (themeIcon) {
      themeIcon.className = 'bx ' + themeIcons[theme];
    }
    if (themeToggle) {
      themeToggle.setAttribute('data-title', themeTitles[theme]);
    }
  }

  function nextTheme(current) {
    const index = themes.indexOf(current);
    return themes[(index + 1) % themes.length];
  }

  function getSavedTheme() {
    // Сначала проверяем Cookie, потом localStorage (на всякий случай), потом дефолт
    return getCookie('site_theme') || localStorage.getItem('theme') || 'auto';
  }

  function setTheme(theme) {
    // 1. Сохраняем в Cookie (на 30 дней) - ЭТО ГЛАВНОЕ ДЛЯ DJANGO
    setCookie('site_theme', theme, 30);
    
    // 2. Сохраняем и в localStorage для мгновенного обновления без перезагрузки страницы
    localStorage.setItem('theme', theme); 
    
    applyTheme(theme);
  }

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const currentTheme = getSavedTheme();
      const newTheme = nextTheme(currentTheme);
      setTheme(newTheme);
      
      // Опционально: можно сделать перезагрузку страницы, чтобы Django сразу увидел новую тему
      // Но лучше оставить как есть, а при переходе на другую страницу (где график) она подхватится сама
    });
  }

  // Отслеживаем системную смену темы
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const savedTheme = getSavedTheme();
    if (savedTheme === 'auto') {
      applyTheme('auto');
    }
  });

  // Применяем сохранённую тему при загрузке
  applyTheme(getSavedTheme());
});