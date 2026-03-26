class Tabs {
  constructor(container) {
    this.container = container;
    this.buttons = container.querySelectorAll('[data-tab]');
    this.panels = container.querySelectorAll('[data-tab-content]');
    this.defaultTab = container.dataset.defaultTab || 'incident';

    this.cookieKey = `tabs:${window.location.pathname}`;

    this.init();
  }

  init() {
    const initialTab = this.getInitialTab();
    this.activateTab(initialTab);

    this.buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        this.activateTab(tab);
        this.saveToCookie(tab);
      });
    });
  }

  getInitialTab() {
    const cookieTab = this.getCookie();

    if (cookieTab) {
      return cookieTab;
    }

    return this.defaultTab;
  }

  activateTab(tab) {
    const exists = [...this.panels].some(
      p => p.dataset.tabContent === tab
    );

    const safeTab = exists ? tab : this.defaultTab;

    this.buttons.forEach(btn => {
      btn.classList.toggle('active-tab', btn.dataset.tab === safeTab);
    });

    this.panels.forEach(panel => {
      panel.classList.toggle(
        'active-tab',
        panel.dataset.tabContent === safeTab
      );
    });
  }

  /* ===== Cookie helpers ===== */

  saveToCookie(tab) {
    const expires = new Date();
    expires.setDate(expires.getDate() + 7); // 7 дней

    document.cookie = `${this.cookieKey}=${tab}; path=${window.location.pathname}; expires=${expires.toUTCString()}`;
  }

  getCookie() {
    const cookies = document.cookie.split(';');

    for (let cookie of cookies) {
      const [key, value] = cookie.trim().split('=');

      if (key === this.cookieKey) {
        return value;
      }
    }

    return null;
  }
}

/* init */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tabs').forEach(tab => {
    new Tabs(tab);
  });
});