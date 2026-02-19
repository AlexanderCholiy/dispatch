document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.multi-select-wrapper').forEach(wrapper => {

    const multiSelect = wrapper.querySelector('.multi-select');
    const valuesContainer = wrapper.querySelector('.multi-select-values');
    const dropdown = wrapper.querySelector('.multi-select-dropdown');
    const options = Array.from(wrapper.querySelectorAll('.multi-select-option'));
    const hiddenInput = wrapper.querySelector('input[type="hidden"]');

    const required = wrapper.dataset.required === "true";

    let selected = hiddenInput.value
      ? hiddenInput.value.split(',').filter(Boolean)
      : [];

    /* ----------------------- */

    function syncInput() {
      hiddenInput.value = selected.join(',');
    }

    function updateDropdownState() {
      options.forEach(option => {
        const isSelected = selected.includes(option.dataset.value);
        option.classList.toggle('selected', isSelected);
      });
    }

    function renderValues() {
      valuesContainer.innerHTML = '';

      selected.forEach(val => {
        const optionEl = options.find(o => o.dataset.value === val);
        if (!optionEl) return;

        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = optionEl.textContent;

        const canRemove = !required || selected.length > 1;

        if (canRemove) {
          const removeBtn = document.createElement('span');
          removeBtn.className = 'remove';
          removeBtn.textContent = '×';

          removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            selected = selected.filter(v => v !== val);
            syncInput();
            updateDropdownState();
            renderValues();
          });

          tag.appendChild(removeBtn);
        }

        valuesContainer.appendChild(tag);
      });

      syncInput();
      updateDropdownState();
    }

    /* ----------------------- */

    // Открытие / закрытие
    multiSelect.addEventListener('click', (e) => {
      if (!e.target.classList.contains('remove')) {
        multiSelect.classList.toggle('open');
      }
    });

    // Выбор из dropdown
    options.forEach(option => {
      option.addEventListener('click', (e) => {
        e.stopPropagation();

        const value = option.dataset.value;
        const isSelected = selected.includes(value);

        if (!isSelected) {
          selected.push(value);
        } else {
          if (required && selected.length === 1) return;
          selected = selected.filter(v => v !== value);
        }

        renderValues();
      });
    });

    // Закрытие при клике вне
    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target)) {
        multiSelect.classList.remove('open');
      }
    });

    renderValues();
  });
});
