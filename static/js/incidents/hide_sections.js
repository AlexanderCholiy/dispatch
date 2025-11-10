document.addEventListener("DOMContentLoaded", function() {
  const toggles = [
    {
      btnSelector: ".toggle-email-three",
      blockSelector: ".email-three",
      cookieName: "emailThreeVisible",
      showText: "Показать письма",
      hideText: "Скрыть письма"
    },
    {
      btnSelector: ".toggle-status-history",
      blockSelector: ".status-history",
      cookieName: "statusHistoryVisible",
      showText: "Показать историю статусов",
      hideText: "Скрыть историю статусов"
    }
  ];

  function setCookie(name, value, days = 365) {
    const d = new Date();
    d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${name}=${value}; path=/; expires=${d.toUTCString()}`;
  }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }

  // --- глобальные кнопки (основные блоки)
  toggles.forEach(item => {
    const button = document.querySelector(item.btnSelector);
    const block = document.querySelector(item.blockSelector);
    if (!button || !block) return;

    if (getCookie(item.cookieName) === "true") {
      block.style.display = "block";
      button.textContent = item.hideText;
    } else {
      block.style.display = "none";
      button.textContent = item.showText;
    }

    button.addEventListener("click", () => {
      const isHidden = block.style.display === "none" || block.style.display === "";
      block.style.display = isHidden ? "block" : "none";
      button.textContent = isHidden ? item.hideText : item.showText;
      setCookie(item.cookieName, String(isHidden));
    });
  });

  // --- обработка веток писем
  document.querySelectorAll(".toggle-tree-btn").forEach(btn => {
    const treeId = btn.dataset.treeId;
    const treeBody = document.querySelector(`#${treeId} .email-tree-body`);
    const storageKey = `treeVisible_${treeId}`;

    // если нет состояния — по умолчанию показываем
    const savedState = localStorage.getItem(storageKey);
    const isVisible = savedState === null ? true : savedState === "true";

    if (isVisible) {
      treeBody.classList.remove("hidden");
      btn.textContent = "Скрыть переписку";
    } else {
      treeBody.classList.add("hidden");
      btn.textContent = "Показать переписку";
    }

    btn.addEventListener("click", () => {
      const nowHidden = treeBody.classList.toggle("hidden");
      btn.textContent = nowHidden ? "Показать переписку" : "Скрыть переписку";
      localStorage.setItem(storageKey, String(!nowHidden));
    });
  });
});
