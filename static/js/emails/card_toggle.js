document.addEventListener("DOMContentLoaded", () => {
  const wrapper = document.getElementById("emails-wrapper");
  if (!wrapper) return;

  // Раскрытие тела письма
  wrapper.addEventListener("click", (event) => {
    if (event.target.closest("a")) return;

    const toggleZone = event.target.closest(".email-row-bottom");
    if (!toggleZone) return;

    const card = toggleZone.closest(".email-card");
    if (!card) return;

    const body = card.querySelector(".email-body");
    if (!body) return;

    if (body.classList.contains("open")) {
      body.style.maxHeight = null;
      body.style.paddingTop = null;
      body.style.paddingBottom = null;
      body.style.opacity = 0;
      body.classList.remove("open");
      card.classList.remove("open");
    } else {
      body.classList.add("open");
      card.classList.add("open");
      body.style.opacity = 1;

      // Пересчёт maxHeight с учётом всех изображений
      const images = body.querySelectorAll("img");
      let loaded = 0;
      const recalcHeight = () => {
        body.style.maxHeight = body.scrollHeight + "px";
      };

      if (images.length === 0) recalcHeight();
      else {
        images.forEach(img => {
          if (img.complete) loaded++;
          else img.onload = () => {
            loaded++;
            if (loaded === images.length) recalcHeight();
          };
        });
        if (loaded === images.length) recalcHeight();
      }
      requestAnimationFrame(recalcHeight);
    }
  });

  // Раскрытие вложений
  wrapper.addEventListener("click", (event) => {
    const btn = event.target.closest(".toggle-attachments-btn");
    if (!btn) return;

    const attachments = btn.nextElementSibling;
    if (!attachments) return;

    const body = btn.closest(".email-body");
    if (!body) return;

    attachments.classList.toggle("hidden");
    btn.textContent = attachments.classList.contains("hidden") ? "Показать вложения" : "Скрыть вложения";

    // Пересчёт maxHeight родительского body
    requestAnimationFrame(() => {
      body.style.maxHeight = body.scrollHeight + "px";
    });
  });
});
