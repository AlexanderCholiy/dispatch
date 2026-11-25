const PREFIX_MARK = '__prefix__';
const ADD_ROW_BTN_ID = 'stages-add-row';
const EMPTY_ROW_TPL_ID = 'stages-empty-row';
const TBODY_SELECTOR = '.stages-tbody';
const ROW_SELECTOR = 'tr.stages-row';

export class StagesForm {
  constructor(form) {
    this.form = form;
    this.management = form.querySelector('[name$="-TOTAL_FORMS"]');
    if (!this.management) return;

    this.prefix = this.management.name.replace(/-TOTAL_FORMS$/, '');
    this.maxInput = form.querySelector(`[name="${this.prefix}-MAX_NUM_FORMS"]`);
    this.tbody = form.querySelector(TBODY_SELECTOR);
    this.addBtn = document.getElementById(ADD_ROW_BTN_ID);
    this.template = document.getElementById(EMPTY_ROW_TPL_ID);

    this.init();
  }

  get maxForms() {
    return Number(this.maxInput?.value || 0);
  }

  get totalForms() {
    return Number(this.management.value);
  }

  set totalForms(value) {
    this.management.value = String(value);
  }

  init() {
    if (!this.tbody || !this.template) return;

    this.addBtn?.addEventListener('click', () => this.addRow());
    this.form.addEventListener('submit', () => this.dropEmptyRows());

    this.tbody.addEventListener('change', (event) => {
      const box = event.target.closest('input[type="checkbox"][name$="-DELETE"]');
      if (box) {
        box.closest(ROW_SELECTOR)?.classList.toggle('is-deleted', box.checked);
      }
    });
  }

  get rows() {
    return [...this.tbody.querySelectorAll(ROW_SELECTOR)];
  }

  rowIndex(row) {
    const control = row.querySelector('[name]');
    const match = control?.name.match(new RegExp(`${this.prefix}-(\\d+)-`));
    return match ? Number(match[1]) : null;
  }

  addRow() {
    if (this.maxForms && this.totalForms >= this.maxForms) {
      this.showLimitHint();
      return;
    }

    const html = this.template.innerHTML.replaceAll(
      PREFIX_MARK,
      String(this.totalForms),
    );
    const holder = document.createElement('tbody');
    holder.innerHTML = html.trim();

    const row = holder.querySelector(ROW_SELECTOR);
    if (!row) return;

    row.dataset.dynamic = '1';
    this.tbody.appendChild(row);
    this.totalForms += 1;
    row.querySelector('select, input')?.focus();
  }

  /** Не отправляем на сервер полностью пустые новые строки. */
  dropEmptyRows() {
    const doomed = this.rows.filter((row) => {
      if (row.querySelector('input[type="hidden"]')?.value) return false;
      const filled = [...row.querySelectorAll(
        'select, input[type="text"], input[type="datetime-local"]',
      )].some((el) => el.value && el.value.trim() !== '');
      return !filled;
    });

    if (!doomed.length) return;

    doomed.forEach((row) => row.remove());
    this.reindex();
  }

  /** Пересобираем индексы оставшихся строк подряд: 0, 1, 2 ... */
  reindex() {
    this.rows.forEach((row, index) => {
      row.querySelectorAll('[name], label[for], [id]').forEach((el) => {
        ['name', 'id', 'for'].forEach((attr) => {
          const value = el.getAttribute(attr);
          if (!value) return;
          const updated = value.replace(
            new RegExp(`(${this.prefix})-\\d+-`),
            `$1-${index}-`,
          );
          if (updated !== value) el.setAttribute(attr, updated);
        });
      });
    });
    this.totalForms = this.rows.length;
  }

  showLimitHint() {
    if (!this.addBtn) return;
    this.addBtn.disabled = true;
    this.addBtn.title = `Максимум ${this.maxForms} записей`;
    clearTimeout(this._hintTimer);
    this._hintTimer = setTimeout(() => {
      this.addBtn.disabled = false;
      this.addBtn.removeAttribute('title');
    }, 2500);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('.stages-form');
  if (form) new StagesForm(form);
});