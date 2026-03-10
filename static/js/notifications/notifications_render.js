import { openPanel } from './notifications_toggle.js';

export function renderNotifications(listEl, notifications, markReadFn, panel) {
    listEl.innerHTML = "";
    notifications.forEach(n => addNotification(listEl, n, markReadFn, panel, false));
}

export function addNotification(listEl, n, markReadFn, panel, showPanel = true) {
    // Проверка на дубли
    const existing = listEl.querySelector(`.notification-item[data-id='${n.id}']`);
    if (existing) {
        removeNotification(existing);  // удаляем старый элемент
    }

    const el = document.createElement("div");
    el.classList.add("notification-item", `notification-${(n.level || 'low').toLowerCase()}`);

    const title = n.title || "Без темы";
    const message = n.message || "";
    const sent_at = n.send_at ? new Date(n.send_at) : new Date();
    const dateStr = isNaN(sent_at.getTime()) ? "" : sent_at.toLocaleString();

    el.dataset.id = n.id;
    el.innerHTML = `
        <div class="notification-title copy-text" data-text="${title}">${title}</div>
        <div class="notification-message">${message}</div>
        <div class="notification-footer">
            <span class="notification-date">${dateStr}</span>
            <button class="btn btn-secondary notification-mark-read">Прочитано</button>
        </div>
    `;

    el.querySelector(".notification-mark-read").onclick = (e) => {
        e.stopPropagation();
        markReadFn(n.id);
        removeNotification(el);
    };

    listEl.prepend(el);  // вставляем новое уведомление в начало
    requestAnimationFrame(() => el.classList.add("show"));

    if (showPanel && n.level === "high" && panel.style.display !== "block") {
        openPanel(panel);
    }
}

export function removeNotification(el) {
    el.classList.remove("show");
    el.addEventListener("transitionend", () => el.remove(), { once: true });
}

export function updateCount(countEl, count) {
    if (count > 0) {
        countEl.innerText = count;
        countEl.style.display = "inline-block";
    } else {
        countEl.style.display = "none";
    }
}

// Делегированное копирование текста
export function initCopy(listEl, messagesContainer) {
    if (!listEl || !messagesContainer) return;
    listEl.addEventListener("click", (e) => {
        const target = e.target.closest(".copy-text");
        if (!target) return;
        const text = target.dataset.text || target.innerText || "";
        if (!text) return;

        navigator.clipboard.writeText(text).then(() => {
            const msg = document.createElement("div");
            msg.className = "message alert-info";
            msg.innerText = text.length > 100 ? "Данные скопированы в буфер обмена" : `${text} скопирован в буфер`;
            messagesContainer.appendChild(msg);
            setTimeout(() => msg.remove(), 5000);
        }).catch(() => {
            const msg = document.createElement("div");
            msg.className = "message alert-error";
            msg.innerText = "Не удалось скопировать данные";
            messagesContainer.appendChild(msg);
            setTimeout(() => msg.remove(), 5000);
        });
    });
}