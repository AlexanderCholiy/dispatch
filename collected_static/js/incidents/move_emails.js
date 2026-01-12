document.addEventListener('DOMContentLoaded', () => {
  const checkboxes = document.querySelectorAll('.email-tree-checkbox');
  const moveBtn = document.getElementById('move-emails-btn');
  const form = document.getElementById('move-emails-form');
  const hiddenField = document.getElementById(window.MOVE_EMAILS_CONFIG.idEmailIds);
  const incidentInput = document.getElementById(window.MOVE_EMAILS_CONFIG.targetIncidentInputId);
  const messagesContainer = document.querySelector('.messages-container');

  if (!checkboxes.length || !moveBtn || !form || !incidentInput || !hiddenField || !messagesContainer) return;

  // Функция для вывода сообщения
  const showMessage = (text, type = 'error') => {
    const div = document.createElement('div');
    div.className = `message alert-${type}`;
    div.textContent = text;
    messagesContainer.appendChild(div);
  };

  // Убираем все старые сообщения
  const clearMessages = () => {
    messagesContainer.innerHTML = '';
  };

  // Обновление скрытого поля, кнопки и класса chosen
  const updateState = () => {
    const selectedGroups = [];
    checkboxes.forEach(cb => {
      const emailTree = cb.closest('.email-tree');
      if (cb.checked) {
        try {
          const ids = JSON.parse(cb.getAttribute('data-ids'));
          selectedGroups.push(ids);
          emailTree.classList.add('chosen'); // добавляем класс
        } catch {
          // пропускаем, если невалидный JSON
        }
      } else {
        emailTree.classList.remove('chosen'); // убираем класс
      }
    });
    hiddenField.value = JSON.stringify(selectedGroups);
    moveBtn.disabled = selectedGroups.length === 0;
  };

  // Состояние кнопки при загрузке
  updateState();

  // Навешиваем обработчик на каждый чекбокс
  checkboxes.forEach(cb => cb.addEventListener('change', updateState));

  // Отправка формы
  form.addEventListener('submit', (e) => {
    clearMessages();

    // Проверка чекбоксов
    const selectedGroups = JSON.parse(hiddenField.value || '[]');
    if (!selectedGroups.length) {
      e.preventDefault();
      showMessage('Выберите хотя бы одну цепочку писем.', 'error');
      return;
    }

    // Проверка кода инцидента
    const value = incidentInput.value.trim();
    const regex = /^[A-Za-z0-9-]+$/;
    if (!regex.test(value)) {
      e.preventDefault();
      showMessage('Код инцидента может содержать только латинские буквы, цифры и дефис.', 'error');
      incidentInput.focus();
      return;
    }
  });
});
