document.addEventListener('DOMContentLoaded', () => {
  const texts = document.querySelectorAll('.copy-text');
  const messagesContainer = document.querySelector('.messages-container');

  texts.forEach(textEl => {
    textEl.style.cursor = 'pointer';

    textEl.addEventListener('click', () => {
      const text = textEl.getAttribute('data-text') || '';
      navigator.clipboard.writeText(text)
        .then(() => {
          const message = document.createElement('div');
          message.className = 'message alert-info';

          if (text.length > 100) {
            message.innerText = `Данные скопированы в буфер обмена`;
          } else {
            message.innerText = `${text} скопирован в буфер`;
          }

          messagesContainer.appendChild(message);

          setTimeout(() => message.remove(), 5000);
        })
        .catch(err => {
          console.error('Ошибка копирования: ', err);
          const message = document.createElement('div');
          message.className = 'message alert-error';
          message.innerText = `Не удалось скопировать данные`;
          messagesContainer.appendChild(message);
          setTimeout(() => message.remove(), 5000);
        });
    });
  });
});
