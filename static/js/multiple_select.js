document.addEventListener('DOMContentLoaded', function() {
  const wrappers = document.querySelectorAll('.multiple-select-wrapper');

  wrappers.forEach(wrapper => {
    const trigger = wrapper.querySelector('.dropdown-trigger');
    const menu = wrapper.querySelector('.dropdown-menu');
    const hiddenSelect = wrapper.querySelector('select[multiple]');
    const options = wrapper.querySelectorAll('.option-item');
    const labelSpan = wrapper.querySelector('.selected-label');

    if (!trigger || !menu || !hiddenSelect) return;

    let filterName = trigger.getAttribute('data-filter-name') || 'Фильтр';
    
    // Считаем только реальные опции (не пустые)
    const realOptionsCount = Array.from(options).filter(opt => opt.dataset.value !== '').length;

    // --- ДОБАВЛЕНИЕ КНОПКИ "ВЫБРАТЬ ВСЕ / СНЯТЬ ВСЕ" ---
    // Проверяем, не создана ли уже кнопка (для надежности)
    if (!menu.querySelector('.select-all-toggle')) {
        const selectAllBtn = document.createElement('div');
        selectAllBtn.className = 'select-all-toggle';
        
        const optionsContainer = menu.querySelector('.dropdown-options');
        if (optionsContainer) {
            optionsContainer.insertBefore(selectAllBtn, optionsContainer.firstChild);
        } else {
            // Если контейнера нет, добавляем перед первым элементом или в конец
            if (options.length > 0) {
                menu.insertBefore(selectAllBtn, options[0]);
            } else {
                menu.appendChild(selectAllBtn);
            }
        }

        // Функция обновления текста кнопки
        function updateSelectAllBtn() {
          const selectedRealCount = Array.from(options).filter(opt => opt.classList.contains('is-selected') && opt.dataset.value !== '').length;
          
          if (selectedRealCount === realOptionsCount) {
            selectAllBtn.textContent = 'Снять все';
            selectAllBtn.classList.add('btn-deselect');
            selectAllBtn.classList.remove('btn-select');
          } else {
            selectAllBtn.textContent = 'Выбрать все';
            selectAllBtn.classList.add('btn-select');
            selectAllBtn.classList.remove('btn-deselect');
          }
        }

        // Обработчик клика по кнопке
        selectAllBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          
          const selectedRealCount = Array.from(options).filter(opt => opt.classList.contains('is-selected') && opt.dataset.value !== '').length;
          const shouldSelectAll = selectedRealCount < realOptionsCount;

          options.forEach(opt => {
            // Пропускаем опцию "Все" (пустое значение)
            if (opt.dataset.value === '') return;

            if (shouldSelectAll) {
              opt.classList.add('is-selected');
            } else {
              opt.classList.remove('is-selected');
            }

            const optionInSelect = hiddenSelect.querySelector(`option[value="${opt.dataset.value}"]`);
            if (optionInSelect) {
              optionInSelect.selected = shouldSelectAll;
            }
          });

          updateLabel();
          updateSelectAllBtn();
        });
    }

    // --- ЛОГИКА ОБНОВЛЕНИЯ ПОДПИСИ (LABEL) ---
    function updateLabel() {
      const selectedItems = Array.from(options).filter(item => item.classList.contains('is-selected'));
      const hasOnlyAllOption = selectedItems.length === 1 && selectedItems[0].dataset.value === '';
      const isEmpty = selectedItems.length === 0;

      if (isEmpty || hasOnlyAllOption) {
        labelSpan.textContent = `${filterName}: Все`;
      } else {
        const selectedRealCount = selectedItems.filter(opt => opt.dataset.value !== '').length;
        
        if (selectedRealCount === realOptionsCount) {
          labelSpan.textContent = `${filterName}: Все`;
        } else if (selectedRealCount === 1) {
          const singleItem = selectedItems.find(opt => opt.dataset.value !== '');
          if (singleItem) {
            const text = singleItem.querySelector('span').textContent;
            labelSpan.textContent = `${filterName}: ${text}`;
          }
        } else {
          labelSpan.textContent = `${filterName}: ${selectedRealCount} шт.`;
        }
      }
      // Обновляем состояние кнопки после изменения лейбла
      updateSelectAllBtn();
    }

    // Открытие/закрытие меню
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.contains('open');

      // Закрываем ВСЕ открытые меню на странице, кроме текущего
      document.querySelectorAll('.dropdown-menu.open').forEach(m => {
        if (m !== menu) {
          m.classList.remove('open');
          const otherTrigger = m.closest('.multiple-select-wrapper').querySelector('.dropdown-trigger');
          if (otherTrigger) otherTrigger.classList.remove('active');
        }
      });

      if (!isOpen) {
        menu.classList.add('open');
        trigger.classList.add('active');
      } else {
        menu.classList.remove('open');
        trigger.classList.remove('active');
      }
    });

    // Закрытие при клике вне меню
    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target)) {
        menu.classList.remove('open');
        trigger.classList.remove('active');
      }
    });

    // Обработка кликов по обычным опциям
    options.forEach(opt => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        
        const value = opt.dataset.value;
        if (value === '') return; 

        const isCurrentlySelected = opt.classList.contains('is-selected');

        if (isCurrentlySelected) {
          opt.classList.remove('is-selected');
        } else {
          opt.classList.add('is-selected');
        }

        const optionInSelect = hiddenSelect.querySelector(`option[value="${value}"]`);
        if (optionInSelect) {
          optionInSelect.selected = !isCurrentlySelected;
        }

        updateLabel();
      });
    });

    // Первичное обновление
    updateLabel();
  });
});