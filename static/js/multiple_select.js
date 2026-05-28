document.addEventListener('DOMContentLoaded', function() {
  const wrappers = document.querySelectorAll('.multiple-select-wrapper');

  wrappers.forEach(wrapper => {
    const trigger = wrapper.querySelector('.dropdown-trigger');
    const menu = wrapper.querySelector('.dropdown-menu');
    const hiddenSelect = wrapper.querySelector('select[multiple]');
    const options = wrapper.querySelectorAll('.option-item');
    const labelSpan = wrapper.querySelector('.selected-label');

    if (!trigger || !menu || !hiddenSelect) return;

    // Получаем имя фильтра
    let filterName = trigger.getAttribute('data-filter-name') || 'Фильтр';
    
    // Считаем общее количество реальных опций (исключая "Все", если оно есть с пустым value)
    // Находим все опции, у которых value НЕ пустой
    const realOptionsCount = Array.from(options).filter(opt => opt.dataset.value !== '').length;

    function updateLabel() {
      const selectedItems = Array.from(options).filter(item => item.classList.contains('is-selected'));
      
      // 1. Если ничего не выбрано ИЛИ выбрана только опция "Все" (value="" )
      const hasOnlyAllOption = selectedItems.length === 1 && selectedItems[0].dataset.value === '';
      const isEmpty = selectedItems.length === 0;

      if (isEmpty || hasOnlyAllOption) {
        labelSpan.textContent = `${filterName}: Все`;
        return;
      }

      // 2. Если выбраны ВСЕ доступные опции (кроме "Все")
      // Проверяем, что количество выбранных (без учета "Все") равно общему количеству опций
      const selectedRealCount = selectedItems.filter(opt => opt.dataset.value !== '').length;
      
      if (selectedRealCount === realOptionsCount) {
        labelSpan.textContent = `${filterName}: Все`;
        return;
      }

      // 3. Если выбрано ровно ОДНА реальная опция
      if (selectedRealCount === 1) {
        const singleItem = selectedItems.find(opt => opt.dataset.value !== '');
        if (singleItem) {
          const text = singleItem.querySelector('span').textContent;
          labelSpan.textContent = `${filterName}: ${text}`;
          return;
        }
      }

      // 4. Если выбрано больше одной опции (но не все)
      labelSpan.textContent = `${filterName}: выбрано ${selectedRealCount}`;
    }

    // Открытие/закрытие меню
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.contains('open');

      document.querySelectorAll('.dropdown-menu.open').forEach(m => {
        if (m !== menu) m.classList.remove('open');
        const otherTrigger = m.closest('.multiple-select-wrapper').querySelector('.dropdown-trigger');
        if (otherTrigger) otherTrigger.classList.remove('active');
      });

      if (!isOpen) {
        menu.classList.add('open');
        trigger.classList.add('active');
      } else {
        menu.classList.remove('open');
        trigger.classList.remove('active');
      }
    });

    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target)) {
        menu.classList.remove('open');
        trigger.classList.remove('active');
      }
    });

    options.forEach(opt => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        
        const value = opt.dataset.value;
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

    // Инициализация при загрузке страницы
    updateLabel();
  });
});