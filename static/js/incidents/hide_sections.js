document.addEventListener("DOMContentLoaded", function() {
  const toggles = [
    { btnSelector: ".toggle-email-three", blockSelector: ".email-three", cookieName: "emailThreeVisible", showText: "Показать письма", hideText: "Скрыть письма" },
    { btnSelector: ".toggle-status-history", blockSelector: ".status-history", cookieName: "statusHistoryVisible", showText: "Показать историю статусов", hideText: "Скрыть историю статусов" }
  ];

  function setCookie(name, value, days = 365) {
    const d = new Date();
    d.setTime(d.getTime() + (days*24*60*60*1000));
    document.cookie = `${name}=${value}; path=/; expires=${d.toUTCString()}`;
  }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }

  toggles.forEach(item => {
    const button = document.querySelector(item.btnSelector);
    const block = document.querySelector(item.blockSelector);
    if (!button || !block) return;

    // Начальное состояние из куки
    if (getCookie(item.cookieName) === "true") {
      block.style.display = "block";
      button.textContent = item.hideText;
    } else {
      block.style.display = "none";
      button.textContent = item.showText;
    }

    // Обработчик клика
    button.addEventListener("click", () => {
      if (block.style.display === "none" || block.style.display === "") {
        block.style.display = "block";
        button.textContent = item.hideText;
        setCookie(item.cookieName, "true");
      } else {
        block.style.display = "none";
        button.textContent = item.showText;
        setCookie(item.cookieName, "false");
      }
    });
  });
});
