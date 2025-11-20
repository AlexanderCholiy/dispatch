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

  function applyTheme(theme) {
    // Убираем старые темы
    html.classList.remove('light', 'dark');

    if (theme === 'light') {
      html.classList.add('light');
    } else if (theme === 'dark') {
      html.classList.add('dark');
    } else if (theme === 'auto') {
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
    return localStorage.getItem('theme') || 'auto';
  }

  function setTheme(theme) {
    localStorage.setItem('theme', theme);
    applyTheme(theme);
  }

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const currentTheme = getSavedTheme();
      const newTheme = nextTheme(currentTheme);
      setTheme(newTheme);
    });
  }

  // Отслеживаем системную смену темы
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (getSavedTheme() === 'auto') {
      applyTheme('auto');
    }
  });

  // Применяем сохранённую тему при загрузке
  applyTheme(getSavedTheme());
});
