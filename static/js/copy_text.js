document.addEventListener('DOMContentLoaded', () => {
  const texts = document.querySelectorAll('.copy-text');
  const messagesContainer = document.querySelector('.messages-container');

  texts.forEach(textEl => {
    textEl.style.cursor = 'pointer';

    textEl.addEventListener('click', () => {
      const text = textEl.getAttribute('data-text');
      navigator.clipboard.writeText(text)
        .then(() => {
          const message = document.createElement('div');
          message.className = 'message alert-warning';
          message.innerText = `${text} скопирован в буфер`;

          messagesContainer.appendChild(message);

          setTimeout(() => {
            message.remove();
          }, 5000);
        })
        .catch(err => {
          console.error('Ошибка копирования: ', err);
          const message = document.createElement('div');
          message.className = 'message alert-error';
          message.innerText = `Не удалось скопировать ${text}`;
          messagesContainer.appendChild(message);
          setTimeout(() => message.remove(), 5000);
        });
    });
  });
});