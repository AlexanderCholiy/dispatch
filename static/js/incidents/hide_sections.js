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

  // --- обработка кастомных чекбоксов
  document.querySelectorAll(".custom-checkbox-wrapper input[type='checkbox']").forEach(checkbox => {
    const wrapper = checkbox.closest(".custom-checkbox-wrapper");

    // начальное состояние
    if (checkbox.checked) wrapper.classList.add("checked");

    checkbox.addEventListener("change", () => {
      wrapper.classList.toggle("checked", checkbox.checked);
    });
  });

  // --- обработка кликов по ссылкам на письма
  document.querySelectorAll(".email-link").forEach(link => {
    link.addEventListener("click", event => {
      event.preventDefault();

      const targetId = link.getAttribute("href").replace("#", "");
      const targetElement = document.getElementById(targetId);
      if (!targetElement) return;

      // если письмо находится в скрытом дереве — раскрываем его
      const treeBody = targetElement.closest(".email-tree-body");
      if (treeBody && treeBody.classList.contains("hidden")) {
        const toggleBtn = treeBody
          .closest(".email-tree")
          .querySelector(".toggle-tree-btn");

        treeBody.classList.remove("hidden");
        if (toggleBtn) {
          toggleBtn.textContent = "Скрыть переписку";
        }

        // сохраняем состояние
        const treeId = treeBody.closest(".email-tree")?.id;
        if (treeId) localStorage.setItem(`treeVisible_${treeId}`, "true");
      }

      // плавный скролл к письму
      targetElement.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });

      // подсветка письма (анимация)
      targetElement.classList.add("email-highlight");
      setTimeout(() => targetElement.classList.remove("email-highlight"), 2000);
    });
  });
});
